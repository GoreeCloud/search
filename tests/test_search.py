"""Offline, isolated acceptance tests for original GoreeCloud Search foundation."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from goreecloud_search.server import SearchServer
from goreecloud_search.store import InvalidDocument, import_jsonl, initialize, safe_url, search


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "private.db"
        initialize(self.db)

    def test_private_index_permissions(self):
        import stat
        self.assertEqual(stat.S_IMODE(self.db.stat().st_mode), 0o600)
        self.db.chmod(0o644)
        with self.assertRaises(PermissionError):
            search(self.db, "private")
        self.db.chmod(0o600)

    def test_init_and_local_search(self):
        data = Path(self.temp.name) / "items.jsonl"
        data.write_text(json.dumps({
            "title": "GoreeCloud Handbook", "description": "Secure personal cloud notes",
            "url": "https://example.org/docs", "source": "approved"
        }) + "\n", encoding="utf-8")
        self.assertEqual(import_jsonl(self.db, data), 1)
        rows = search(self.db, "personal cloud")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "GoreeCloud Handbook")
        self.assertEqual(search(self.db, "notfound"), [])

    def test_fts_syntax_cannot_escape_query(self):
        self.assertEqual(search(self.db, "a\" OR document*"), [])
        for query in ("", " ", "x" * 161):
            with self.assertRaises(ValueError):
                search(self.db, query)
        with self.assertRaises(ValueError):
            search(self.db, "hello", True)

    def test_import_is_atomic_on_invalid_row(self):
        data = Path(self.temp.name) / "items.jsonl"
        data.write_text(json.dumps({
            "title": "Present", "description": "A safe record",
            "url": "https://example.org/a"
        }) + "\n", encoding="utf-8")
        import_jsonl(self.db, data)
        data.write_text(
            json.dumps({"title": "New", "description": "Second record", "url": "https://example.org/new"})
            + "\n" + '{"title":"invalid","description":"Bad","url":"javascript:alert(1)"}\n',
            encoding="utf-8")
        with self.assertRaises(InvalidDocument):
            import_jsonl(self.db, data)
        self.assertEqual(len(search(self.db, "present")), 1)
        self.assertEqual(search(self.db, "second"), [])

    def test_result_link_validation(self):
        for url in ("http://example.org", "javascript:alert(1)", "https://localhost/x",
                    "https://127.0.0.1/private", "https://10.0.0.1/x",
                    "https://example.org:8443/x", "https://username:pass@example.org/x"):
            with self.subTest(url=url), self.assertRaises(InvalidDocument):
                safe_url(url)
        self.assertEqual(safe_url("https://example.org/reference"), "https://example.org/reference")


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "private.db"
        initialize(self.db)
        data = Path(self.temp.name) / "input.jsonl"
        data.write_text(json.dumps({
            "title": "First-party Search", "description": "An original local index",
            "url": "https://example.org/search", "source": "curated"
        }), encoding="utf-8")
        import_jsonl(self.db, data)
        self.server = SearchServer(("127.0.0.1", 0), self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._shutdown)

    def _shutdown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_health_and_ui_security_headers(self):
        code, headers, body = self.request("GET", "/healthz")
        self.assertEqual(code, 200)
        self.assertIn(b"loopback", body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        code, _, html = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn(b"GoreeCloud Search", html)
        self.assertNotIn(b"searx", html.lower())

    def test_post_search_and_no_get_api(self):
        data = json.dumps({"query": "original local"}).encode()
        code, _, body = self.request("POST", "/api/search", data, {
            "Content-Type": "application/json", "Content-Length": str(len(data))
        })
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["count"], 1)
        code, _, _ = self.request("GET", "/api/search?query=original")
        self.assertEqual(code, 404)

    def test_origin_and_body_guards(self):
        body = b'{"query":"search"}'
        headers = {"Content-Type": "application/json", "Content-Length": str(len(body)),
                   "Origin": "https://attacker.example"}
        code, _, _ = self.request("POST", "/api/search", body, headers)
        self.assertEqual(code, 403)
        code, _, _ = self.request("POST", "/api/search", b"{}", {
            "Content-Type": "text/plain", "Content-Length": "2"})
        self.assertEqual(code, 415)

    def test_nonloopback_bind_rejected(self):
        with self.assertRaises(ValueError):
            SearchServer(("0.0.0.0", 0), self.db)


if __name__ == "__main__":
    unittest.main()
