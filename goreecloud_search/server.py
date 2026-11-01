"""Small HTTP boundary around the independently built local search index."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .store import search
from .providers import ProviderConfig, choose_providers
from .federation import search as federated_search

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
        self.provider_config = ProviderConfig.from_environment()


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

    def _trusted_host(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        return len(hosts) == 1 and hosts[0] == f"127.0.0.1:{self.server.server_port}"

    def _reject(self, code: int, explanation: str) -> None:
        # Refuse to parse unread request bodies on a reused HTTP/1.1 connection.
        self.close_connection = True
        self._json(code, {"error": explanation})

    def do_GET(self) -> None:
        if not self._trusted_host():
            self._reject(421, "Invalid request host")
            return
        if self.path == "/api/providers":
            self._json(200, {
                "available": self.server.provider_config.availability(),
                "default": ["local"],
                "external_requires_consent": True,
            })
            return
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
        if not self._trusted_host():
            self._reject(421, "Invalid request host")
            return
        if self.path != "/api/search":
            self._reject(404, "Not found")
            return
        origins = self.headers.get_all("Origin", [])
        expected_origin = f"http://127.0.0.1:{self.server.server_port}"
        if len(origins) > 1 or (origins and origins[0] != expected_origin):
            self._reject(403, "Cross-origin searches disabled")
            return
        sites = self.headers.get_all("Sec-Fetch-Site", [])
        if len(sites) > 1 or (sites and sites[0] not in ("none", "same-origin")):
            self._reject(403, "Cross-site searches disabled")
            return
        if self.headers.get("Transfer-Encoding"):
            self._reject(400, "Streaming bodies unsupported")
            return
        values = self.headers.get_all("Content-Length", [])
        if len(values) != 1 or not values[0].isascii() or not values[0].isdigit():
            self._reject(411, "Content-Length required")
            return
        size = int(values[0])
        if size < 2 or size > MAX_BODY:
            self._reject(413, "Request too large or empty")
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self._reject(415, "JSON content required")
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
        if (not isinstance(query, str) or not 1 <= len(query.strip()) <= 160
                or type(limit) is not int or not 1 <= limit <= 20):
            self._json(400, {"error": "Invalid query or limit"})
            return
        try:
            sources = choose_providers(
                payload.get("providers"), payload.get("share_query"),
                self.server.provider_config,
            )
        except ValueError:
            self._json(400, {"error": "Invalid provider choice or external consent"})
            return
        try:
            if sources == ["local"]:
                results = search(self.server.db_path, query, limit)
                warnings = []
            else:
                outcome = federated_search(
                    query, limit, sources, self.server.provider_config,
                    lambda q, count: search(self.server.db_path, q, count),
                )
                results, warnings = outcome.results, outcome.warnings
        except Exception:
            # Do not disclose internal errors, queries, or provider credentials.
            self._json(503, {"error": "Search unavailable"})
            return
        self._json(200, {
            "results": results,
            "count": len(results),
            "scope": "federated" if sources != ["local"] else "local-only",
            "providers": sources,
            "warnings": warnings,
        })

    def do_OPTIONS(self) -> None:
        self._reject(405 if self._trusted_host() else 421, "Unsupported method")

    def do_HEAD(self) -> None:
        self.close_connection = True
        self.send_response(405 if self._trusted_host() else 421)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def run_server(db_path: Path, port: int = 8787) -> None:
    server = SearchServer(("127.0.0.1", port), db_path)
    try:
        print(f"GoreeCloud Search (local-only): http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
