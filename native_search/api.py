# SPDX-License-Identifier: AGPL-3.0-or-later
"""Loopback-only, query-private JSON API for GoreeCloud's native index."""
from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import urlsplit

from .index import SearchIndex

MAX_POST_BYTES = 4096


def make_handler(index: SearchIndex):
    class NativeHandler(BaseHTTPRequestHandler):
        server_version = 'GoreeCloudNativeSearchDevelopment'
        sys_version = ''

        def log_message(self, _format, *_args):
            # Do not log user queries, request URLs, or client identifiers.
            return

        def respond(self, status: int, payload: dict) -> None:
            data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            self.send_response(status)
            for key, value in (
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Content-Length', str(len(data))),
                ('Cache-Control', 'no-store'),
                ('Pragma', 'no-cache'),
                ('Referrer-Policy', 'no-referrer'),
                ('X-Content-Type-Options', 'nosniff'),
                ('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'"),
            ):
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def authorized_host(self) -> bool:
            """Deny DNS-rebinding Host headers even on the loopback listener."""
            raw = self.headers.get('Host', '')
            if not raw or raw != raw.strip() or any(ord(ch) <= 32 for ch in raw):
                return False
            try:
                target = urlsplit('http://' + raw)
                return (target.netloc == raw and target.hostname in ('127.0.0.1', 'localhost')
                        and target.port == self.server.server_port
                        and target.username is None and target.password is None
                        and not target.path and not target.query and not target.fragment)
            except ValueError:
                return False

        def do_GET(self):
            if not self.authorized_host():
                return self.respond(403, {'error': 'Host is not a loopback listener'})
            if '?' in self.path:
                return self.respond(405, {'error': 'Query parameters are prohibited'})
            if self.path == '/healthz':
                return self.respond(200, {'status': 'ok', 'mode': 'native-development'})
            if self.path == '/v1/search':
                return self.respond(405, {'error': 'Search requires JSON POST'})
            return self.respond(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.authorized_host():
                return self.respond(403, {'error': 'Host is not a loopback listener'})
            if self.path != '/v1/search':
                return self.respond(404 if '?' not in self.path else 405, {'error': 'Unknown endpoint'})
            if self.headers.get('Origin'):
                return self.respond(403, {'error': 'Browser-origin submissions are not enabled'})
            if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                return self.respond(415, {'error': 'JSON content type required'})
            try:
                length = int(self.headers.get('Content-Length', '-1'))
                if not 1 <= length <= MAX_POST_BYTES:
                    raise ValueError()
                data = self.rfile.read(length)
                supplied = json.loads(data)
                if not isinstance(supplied, dict) or set(supplied) - {'query', 'limit'}:
                    raise ValueError()
                hits = index.search(supplied.get('query'), limit=supplied.get('limit', 10))
            except (ValueError, UnicodeError, TypeError, json.JSONDecodeError):
                return self.respond(422, {'error': 'Invalid bounded search request'})
            return self.respond(200, {
                'source': 'goreecloud-native-index',
                'total_displayed': len(hits),
                'results': [asdict(h) for h in hits],
            })
    return NativeHandler


def run_loopback(index: SearchIndex, *, port: int = 8789) -> None:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Choose a nonprivileged loopback port')
    server = HTTPServer(('127.0.0.1', port), make_handler(index))
    try:
        print('Native Search development API: http://127.0.0.1:%d' % port)
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
