"""Small HTTP boundary around the independently built local search index."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .store import search

WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "connect-src 'self'; img-src 'self' data:; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
MAX_BODY = 8192


class SearchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], db_path: Path):
        if address[0] != "127.0.0.1":
            raise ValueError("Only explicit IPv4 loopback is supported without authentication")
        super().__init__(address, SearchHandler)
        self.db_path = db_path


class SearchHandler(BaseHTTPRequestHandler):
    server: SearchServer
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, _format: str, *args: object) -> None:
        # Deliberately never log user queries, request payloads, or URLs.
        return

    def _send(self, status: int, data: bytes, media_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, body: dict[str, Any]) -> None:
        self._send(status, json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json(200, {"status": "ok", "scope": "loopback"})
            return
        resources = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
        }
        resource = resources.get(self.path)
        if resource is None:
            self._json(404, {"error": "Not found"})
            return
        name, content_type = resource
        try:
            self._send(200, (WEB_ROOT / name).read_bytes(), content_type)
        except OSError:
            self._json(503, {"error": "Interface unavailable"})

    def do_POST(self) -> None:
        if self.path != "/api/search":
            self._json(404, {"error": "Not found"})
            return
        origin = self.headers.get("Origin")
        expected_origin = f"http://127.0.0.1:{self.server.server_port}"
        if origin and origin != expected_origin:
            self._json(403, {"error": "Cross-origin searches disabled"})
            return
        if self.headers.get("Transfer-Encoding"):
            self.close_connection = True
            self._json(400, {"error": "Streaming bodies unsupported"})
            return
        values = self.headers.get_all("Content-Length", [])
        if len(values) != 1 or not values[0].isdigit():
            self.close_connection = True
            self._json(411, {"error": "Content-Length required"})
            return
        size = int(values[0])
        if size < 2 or size > MAX_BODY:
            self.close_connection = True
            self._json(413, {"error": "Request too large or empty"})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self.close_connection = True
            self._json(415, {"error": "JSON content required"})
            return
        try:
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
        except (ValueError, UnicodeError):
            self._json(400, {"error": "Invalid JSON"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "Expected a JSON object"})
            return
        query = payload.get("query")
        limit = payload.get("limit", 12)
        try:
            results = search(self.server.db_path, query, limit)
        except (TypeError, ValueError):
            self._json(400, {"error": "Invalid query or limit"})
            return
        except Exception:
            # No internal exception details or provider data cross this boundary.
            self._json(503, {"error": "Local index unavailable"})
            return
        self._json(200, {"results": results, "count": len(results), "scope": "local-only"})

    def do_OPTIONS(self) -> None:
        self._json(405, {"error": "Unsupported method"})

    def do_HEAD(self) -> None:
        self.send_response(405)
        self.send_header("Content-Length", "0")
        self.end_headers()


def run_server(db_path: Path, port: int = 8787) -> None:
    server = SearchServer(("127.0.0.1", port), db_path)
    try:
        print(f"GoreeCloud Search (local-only): http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
