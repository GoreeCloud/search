"""Real loopback HTTP strict JSON/authority regression tests, no provider egress."""
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


class StrictHTTPPayloadTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        db = Path(self.folder.name) / "index.sqlite3"
        initialize(db)
        self.server = SearchServer(("127.0.0.1", 0), db)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self._close)

    def _close(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=3)

    def raw(self, body: bytes, content_types=("application/json",), extra_headers=()):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            connection.putrequest("POST", "/api/search")
            for kind in content_types:
                connection.putheader("Content-Type", kind)
            connection.putheader("Content-Length", str(len(body)))
            for key, value in extra_headers:
                connection.putheader(key, value)
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), json.loads(response.read())
        finally:
            connection.close()

    def test_duplicate_query_fields_fail_closed(self):
        with patch("goreecloud_search.server.federated_search") as remote:
            status, _, payload = self.raw(b'{"query":"first","query":"second"}')
            self.assertEqual((status, payload["error"]), (400, "Invalid JSON"))
            remote.assert_not_called()

    def test_duplicate_consent_fields_fail_closed(self):
        with patch("goreecloud_search.server.federated_search") as remote:
            body = b'{"query":"public","share_query":false,"share_query":true}'
            status, _, payload = self.raw(body)
            self.assertEqual((status, payload["error"]), (400, "Invalid JSON"))
            remote.assert_not_called()

    def test_duplicate_nested_fields_are_rejected_too(self):
        status, _, payload = self.raw(b'{"query":"local","extras":{"key":1,"key":2}}')
        self.assertEqual((status, payload["error"]), (400, "Invalid JSON"))

    def test_nonfinite_literals_fail_closed(self):
        for literal in (b'NaN', b'Infinity', b'-Infinity'):
            with self.subTest(literal=literal):
                body = b'{"query":"local","extra":' + literal + b'}'
                status, _, payload = self.raw(body)
                self.assertEqual((status, payload["error"]), (400, "Invalid JSON"))

    def test_repeated_content_type_rejected_and_connection_closed(self):
        status, headers, payload = self.raw(
            b'{"query":"local"}',
            content_types=("application/json", "application/json"),
        )
        self.assertEqual(status, 415)
        self.assertEqual(headers.get("Connection"), "close")
        self.assertEqual(payload["error"], "JSON content required")

    def test_transfer_encoding_present_even_if_empty_is_rejected(self):
        status, headers, payload = self.raw(
            b'{"query":"local"}',
            extra_headers=(("Transfer-Encoding", ""),),
        )
        self.assertEqual(status, 400)
        self.assertEqual(headers.get("Connection"), "close")
        self.assertEqual(payload["error"], "Streaming bodies unsupported")


if __name__ == "__main__":
    unittest.main()
