"""Offline contracts for the optional first-party Search adapters.

All outbound transports are patched: no real provider traffic or billable calls.
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from goreecloud_search import providers
from goreecloud_search.federation import search as federated_search


class FakeResponse:
    status = 200

    def __init__(self, body, media_type="application/json"):
        self.body = body
        self.media_type = media_type

    def getheader(self, name, default=None):
        return self.media_type if name == "Content-Type" else default

    def read(self, count=-1):
        return self.body[:count]


class FakeConnection:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.closed = False

    def request(self, method, path, body=None, headers=None):
        self.calls.append((method, path, body, headers))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class OptionalProviderTests(unittest.TestCase):
    def test_external_disabled_even_with_key(self):
        with patch.dict(os.environ, {"GC_SEARCH_BRAVE_API_KEY": "dummy-test-only"}, clear=True):
            c = providers.ProviderConfig.from_environment()
        self.assertEqual(c.availability(), {
            "local": True, "brave": False, "searxng": False,
        })

    def test_invalid_configuration_fails_closed(self):
        for value in ("0", "65536", "localhost:8888", "127.0.0.1:8888", "-1"):
            with self.subTest(port=value):
                with patch.dict(os.environ, {"GC_SEARCH_SEARXNG_PORT": value}, clear=True):
                    with self.assertRaises(providers.ProviderConfigError):
                        providers.ProviderConfig.from_environment()
        with patch.dict(os.environ, {"GC_SEARCH_BRAVE_API_KEY": "invalid\nkey"}, clear=True):
            with self.assertRaises(providers.ProviderConfigError):
                providers.ProviderConfig.from_environment()

    def test_consent_required_for_each_external_selection(self):
        config = providers.ProviderConfig(True, "dummy-test-only", 8888, 2, Path("/tmp/gc-test-budget.sqlite3"))
        self.assertEqual(providers.choose_providers(None, False, config), ["local"])
        self.assertEqual(providers.choose_providers(["local"], False, config), ["local"])
        self.assertEqual(providers.choose_providers(["local", "brave"], True, config), ["local", "brave"])
        for selection, consent in [
            (["brave"], False), (["brave"], "true"), (["unknown"], True),
            (["brave", "brave"], True), ([], True),
        ]:
            with self.subTest(selection=selection, consent=consent):
                with self.assertRaises(ValueError):
                    providers.choose_providers(selection, consent, config)

    def test_brave_response_is_sanitized_and_local_links_rejected(self):
        data = {"web": {"results": [
            {"title": "<b>Search &amp; Results</b>",
             "description": "<em>Safe</em> summary", "url": "https://example.org/path"},
            {"title": "Private", "description": "Private", "url": "https://127.0.0.1/internal"},
            {"title": "Script", "description": "Unsafe", "url": "javascript:alert(1)"},
        ]}}
        results = providers.normalize(data, "brave", 10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Search & Results")
        self.assertEqual(results[0]["description"], "Safe summary")
        self.assertEqual(results[0]["provider"], "brave")

    def test_fixed_brave_host_and_header_not_browser_exposed(self):
        reply = FakeResponse(json.dumps({
            "web": {"results": [{"title": "Example", "description": "D",
                                  "url": "https://example.org/x"}]}
        }).encode())
        connection = FakeConnection(reply)
        config = providers.ProviderConfig(True, "dummy-test-only", None, 2, Path("/tmp/gc-test-budget.sqlite3"))
        with patch.object(providers.BRAVE_RATE_GATE, "reserve"):
            with patch.object(providers, "reserve_request"):
                with patch.object(providers.http.client, "HTTPSConnection", return_value=connection) as factory:
                    result = providers.fetch("brave", "topic", 2, config)
        factory.assert_called_once_with("api.search.brave.com", 443, timeout=4)
        self.assertEqual(connection.calls[0][0], "GET")
        self.assertIn("q=topic", connection.calls[0][1])
        self.assertEqual(connection.calls[0][3]["X-Subscription-Token"], "dummy-test-only")
        self.assertTrue(connection.closed)
        self.assertEqual(len(result), 1)

    def test_searxng_fixed_loopback_post(self):
        reply = FakeResponse(b'{"results":[{"title":"T","content":"D","url":"https://example.org/t"}]}')
        connection = FakeConnection(reply)
        config = providers.ProviderConfig(True, "", 8899)
        with patch.object(providers.http.client, "HTTPConnection", return_value=connection) as factory:
            result = providers.fetch("searxng", "topic", 2, config)
        factory.assert_called_once_with("127.0.0.1", 8899, timeout=4)
        self.assertEqual(connection.calls[0][:2], ("POST", "/search"))
        self.assertIn(b"format=json", connection.calls[0][2])
        self.assertEqual(result[0]["source"], "SearXNG")

    def test_federation_deduplicates_by_url_with_source_order(self):
        result = federated_search(
            "query", 5, ["local", "brave"],
            providers.ProviderConfig(True, "dummy-test-only", None, 2, Path("/tmp/gc-test-budget.sqlite3")),
            lambda query, limit: [
                {"title": "Local", "description": "D", "url": "https://example.org/a", "source": "local"},
            ],
            lambda name, query, limit, cfg: [
                {"title": "Duplicate", "description": "D", "url": "https://example.org/a", "source": name},
                {"title": "Unique", "description": "D", "url": "https://example.org/b", "source": name},
            ],
        )
        self.assertEqual([x["title"] for x in result.results], ["Local", "Unique"])
        self.assertEqual(result.warnings, [])

    def test_federation_provider_failure_is_attributed_not_disclosed(self):
        def fail(*args):
            raise RuntimeError("private details must never escape")
        result = federated_search(
            "query", 5, ["local", "brave"], providers.ProviderConfig(),
            lambda q, n: [], fail,
        )
        self.assertEqual(result.results, [])
        self.assertEqual(result.warnings, [{"provider": "brave", "code": "unavailable"}])
        self.assertNotIn("private details", str(result.warnings))


if __name__ == "__main__":
    unittest.main()
