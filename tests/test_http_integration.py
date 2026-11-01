"""Offline integration tests for the actual first-party Search HTTP API.

No external provider is contacted. A temporary 127.0.0.1 listener is used.
"""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from goreecloud_search import providers
from goreecloud_search.federation import FederatedResult
from goreecloud_search.server import SearchServer
from goreecloud_search.store import import_jsonl, initialize


class SearchHTTPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "private.sqlite3"
        initialize(self.db)
        source = Path(self.temp.name) / "data.jsonl"
        source.write_text(json.dumps({
            "title": "Original local search",
            "description": "First party content",
            "url": "https://example.org/local",
            "source": "curated",
        }), encoding="utf-8")
        import_jsonl(self.db, source)
        self.server = SearchServer(("127.0.0.1", 0), self.db)
        self.server.provider_config = providers.ProviderConfig()
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: thread.join(timeout=3))
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, payload=None, headers=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            body = json.dumps(payload).encode("utf-8") if payload is not None else None
            headers = dict(headers or {})
            if body is not None:
                headers.setdefault("Content-Type", "application/json")
            client.request(method, path, body=body, headers=headers)
            reply = client.getresponse()
            return reply.status, dict(reply.getheaders()), reply.read()
        finally:
            client.close()

    def test_discovery_is_local_only_by_default(self):
        status, headers, data = self.request("GET", "/api/providers")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["default"], ["local"])
        self.assertEqual(json.loads(data)["available"], {
            "local": True, "brave": False, "searxng": False,
        })
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_local_index_search_has_no_external_calls(self):
        with patch("goreecloud_search.server.federated_search") as federation:
            status, _, data = self.request("POST", "/api/search", {"query": "original"})
        self.assertEqual(status, 200)
        response = json.loads(data)
        self.assertEqual(response["scope"], "local-only")
        self.assertEqual(response["results"][0]["source"], "curated")
        federation.assert_not_called()

    def test_consent_and_configuration_are_both_required(self):
        self.server.provider_config = providers.ProviderConfig(True, "dummy-test-key", None, 3, Path(self.temp.name) / "budget.sqlite3")
        with patch("goreecloud_search.server.federated_search") as federation:
            for addition in ({}, {"share_query": False}, {"share_query": "true"}):
                status, _, _ = self.request("POST", "/api/search", {
                    "query": "test", "providers": ["brave"], **addition,
                })
                self.assertEqual(status, 400)
            federation.assert_not_called()
        self.server.provider_config = providers.ProviderConfig()
        status, _, _ = self.request("POST", "/api/search", {
            "query": "test", "providers": ["brave"], "share_query": True,
        })
        self.assertEqual(status, 400)

    def test_explicit_opt_in_returns_attributed_results(self):
        self.server.provider_config = providers.ProviderConfig(True, "dummy-test-key", None, 3, Path(self.temp.name) / "budget.sqlite3")
        remote = FederatedResult([{
            "title": "External", "description": "Safe text",
            "url": "https://example.org/remote", "source": "Brave Search", "provider": "brave",
        }], [])
        with patch("goreecloud_search.server.federated_search", return_value=remote) as federation:
            status, _, data = self.request("POST", "/api/search", {
                "query": "topic", "providers": ["local", "brave"], "share_query": True,
            })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["scope"], "federated")
        self.assertEqual(json.loads(data)["results"][0]["provider"], "brave")
        federation.assert_called_once()
        self.assertNotIn(b"dummy-test-key", data)

    def test_forged_host_rejected_on_read_and_write(self):
        for method, path, payload in (
            ("GET", "/api/providers", None),
            ("GET", "/", None),
            ("POST", "/api/search", {"query": "local"}),
        ):
            with self.subTest(path=path):
                status, _, data = self.request(
                    method, path, payload, {"Host": "attacker.example"},
                )
                self.assertEqual(status, 421)
                self.assertNotIn(b"results", data)

    def test_cross_origin_and_fetch_site_rejected(self):
        self.server.provider_config = providers.ProviderConfig(True, "dummy-test-key", None, 3, Path(self.temp.name) / "budget.sqlite3")
        with patch("goreecloud_search.server.federated_search") as federation:
            for headers in (
                {"Origin": "http://attacker.example"},
                {"Sec-Fetch-Site": "cross-site"},
                {"Sec-Fetch-Site": "same-site"},
            ):
                status, _, _ = self.request("POST", "/api/search", {
                    "query": "topic", "providers": ["brave"], "share_query": True,
                }, headers)
                self.assertEqual(status, 403)
            federation.assert_not_called()

    def test_invalid_query_limit_and_duplicate_provider_rejected(self):
        self.server.provider_config = providers.ProviderConfig(True, "dummy-test-key", None, 3, Path(self.temp.name) / "budget.sqlite3")
        for payload in (
            {"query": "", "providers": ["brave"], "share_query": True},
            {"query": "topic", "limit": True, "providers": ["brave"], "share_query": True},
            {"query": "topic", "limit": 21, "providers": ["brave"], "share_query": True},
            {"query": "topic", "providers": ["brave", "brave"], "share_query": True},
        ):
            status, _, _ = self.request("POST", "/api/search", payload)
            self.assertEqual(status, 400)

    def test_partial_failure_has_bounded_nonsecret_warning(self):
        self.server.provider_config = providers.ProviderConfig(True, "dummy-test-key", None, 3, Path(self.temp.name) / "budget.sqlite3")
        warning = FederatedResult([], [{"provider": "brave", "code": "unavailable"}])
        with patch("goreecloud_search.server.federated_search", return_value=warning):
            status, _, data = self.request("POST", "/api/search", {
                "query": "topic", "providers": ["brave"], "share_query": True,
            })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["warnings"], [
            {"provider": "brave", "code": "unavailable"},
        ])
        self.assertNotIn(b"dummy-test-key", data)

    def test_rejected_request_never_waits_for_unread_body(self):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            client.putrequest("POST", "/api/search")
            client.putheader("Origin", "http://attacker.example")
            client.putheader("Content-Type", "application/json")
            client.putheader("Content-Length", "5000")
            client.endheaders()
            self.assertEqual(client.getresponse().status, 403)
        finally:
            client.close()

    def test_unsupported_methods_do_not_bypass_authority(self):
        self.assertEqual(self.request("OPTIONS", "/api/search")[0], 405)
        self.assertEqual(self.request("OPTIONS", "/api/search",
                                      headers={"Host": "attacker.example"})[0], 421)
        self.assertEqual(self.request("HEAD", "/",
                                      headers={"Host": "attacker.example"})[0], 421)


if __name__ == "__main__":
    unittest.main()
