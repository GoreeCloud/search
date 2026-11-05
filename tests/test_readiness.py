"""Readiness versus liveness verification on a disposable loopback Search server."""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from goreecloud_search.server import SearchServer
from goreecloud_search.store import initialize


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "private.sqlite3"
        initialize(self.db)
        self.server = SearchServer(("127.0.0.1", 0), self.db)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=3)

    def request(self, path, headers=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=4,
        )
        try:
            connection.request("GET", path, headers=headers or {})
            reply = connection.getresponse()
            return reply.status, dict(reply.getheaders()), json.loads(reply.read())
        finally:
            connection.close()

    def test_usable_private_index_is_ready_without_disclosing_data(self):
        status, headers, body = self.request("/readyz")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ready", "scope": "local-catalog"})
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("documents", json.dumps(body))
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_liveness_stays_ok_when_local_index_is_missing(self):
        self.db.unlink()
        status, _, status_body = self.request("/healthz")
        self.assertEqual((status, status_body["status"]), (200, "ok"))
        status, _, ready_body = self.request("/readyz")
        self.assertEqual((status, ready_body["status"]), (503, "unavailable"))
        self.assertNotIn(str(self.db), json.dumps(ready_body))

    def test_unsafe_permissions_fail_closed_without_touching_index(self):
        self.db.chmod(0o644)
        try:
            self.assertEqual(self.request("/readyz")[0], 503)
        finally:
            self.db.chmod(0o600)
        self.assertEqual(self.request("/readyz")[0], 200)

    def test_untrusted_host_never_accesses_index(self):
        with patch("goreecloud_search.server.inspect_catalog") as check:
            status, _, body = self.request(
                "/readyz", {"Host": "untrusted.example"},
            )
        self.assertEqual(status, 421)
        self.assertEqual(body["error"], "Invalid request host")
        check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
