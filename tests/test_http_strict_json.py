"""Real loopback HTTP strict JSON/authority regression tests, no provider egress."""
from __future__ import annotations

import http.client
import json
import socket
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

    def get_with_headers(self, headers):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.putrequest("GET", "/readyz")
            for name, value in headers:
                connection.putheader(name, value)
            # No body is transmitted, so rejection must not block reading it.
            connection.endheaders()
            reply = connection.getresponse()
            return reply.status, dict(reply.getheaders()), json.loads(reply.read())
        finally:
            connection.close()

    def test_get_declared_body_rejected_without_waiting_for_unread_bytes(self):
        status, headers, body = self.get_with_headers((("Content-Length", "2000"),))
        self.assertEqual((status, body["error"]), (400, "GET request bodies unsupported"))
        self.assertEqual(headers.get("Connection"), "close")

    def test_get_rejects_transfer_encoding_even_without_body(self):
        status, headers, body = self.get_with_headers((("Transfer-Encoding", "chunked"),))
        self.assertEqual(status, 400)
        self.assertEqual(headers.get("Connection"), "close")
        self.assertEqual(body["error"], "GET request bodies unsupported")

    def test_get_duplicate_zero_content_length_is_rejected(self):
        status, headers, body = self.get_with_headers(
            (("Content-Length", "0"), ("Content-Length", "0")),
        )
        self.assertEqual(status, 400)
        self.assertEqual(headers.get("Connection"), "close")
        self.assertEqual(body["error"], "GET request bodies unsupported")

    def post_without_body(self, length: str):
        """Send only headers: a malformed length must be rejected immediately."""
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3,
        )
        try:
            connection.putrequest("POST", "/api/search")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", length)
            connection.endheaders()
            reply = connection.getresponse()
            return reply.status, dict(reply.getheaders()), json.loads(reply.read())
        finally:
            connection.close()

    def test_truncated_but_valid_json_never_reaches_local_search(self):
        # A valid JSON prefix is NOT a complete request when Content-Length
        # claims more bytes. Half-close writing to trigger a clean short read.
        actual = b'{"query":"private"}'
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=4,
        )
        try:
            connection.putrequest("POST", "/api/search")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(len(actual) + 10))
            with patch("goreecloud_search.server.search") as local:
                with patch("goreecloud_search.server.federated_search") as remote:
                    connection.endheaders(actual)
                    connection.sock.shutdown(socket.SHUT_WR)
                    reply = connection.getresponse()
                    body = json.loads(reply.read())
                    self.assertEqual((reply.status, body["error"]),
                                     (400, "Incomplete request body"))
                    self.assertEqual(reply.getheader("Connection"), "close")
                    local.assert_not_called()
                    remote.assert_not_called()
        finally:
            connection.close()

    def test_very_long_decimal_length_rejected_without_conversion_or_provider(self):
        with patch("goreecloud_search.server.federated_search") as provider:
            status, headers, data = self.post_without_body("9" * 5000)
        self.assertEqual((status, data["error"]), (413, "Request too large or empty"))
        self.assertEqual(headers.get("Connection"), "close")
        provider.assert_not_called()

    def test_leading_zero_length_refused_as_ambiguous_framing(self):
        with patch("goreecloud_search.server.federated_search") as provider:
            for length in ("0002", "00", "01"):
                with self.subTest(length=length):
                    status, headers, body = self.post_without_body(length)
                    self.assertEqual(status, 411)
                    self.assertEqual(headers.get("Connection"), "close")
                    self.assertEqual(body["error"], "Canonical Content-Length required")
            provider.assert_not_called()

    def test_bounded_oversize_length_rejected_before_unread_body(self):
        with patch("goreecloud_search.server.federated_search") as provider:
            status, headers, data = self.post_without_body("8193")
        self.assertEqual((status, data["error"]), (413, "Request too large or empty"))
        self.assertEqual(headers.get("Connection"), "close")
        provider.assert_not_called()

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
