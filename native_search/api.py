# SPDX-License-Identifier: AGPL-3.0-or-later
"""Loopback-only, query-private API for the owned index and offline fusion.

The endpoint exposes no provider-picker or default network adapter. The
native Linux candidate uses a single synchronous HTTPServer worker, which
also caps service-wide concurrent fusion requests to one; per-request async
provider fan-out remains bounded separately by the dispatcher.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Sequence
from urllib.parse import urlsplit

from .dispatch import ProviderBinding, ProviderRights, dispatch_fusion
from .index import SearchIndex, clean_query
from .owned_index_provider import (OWNED_INDEX_EVIDENCE, OWNED_INDEX_SOURCE,
                                   OwnedIndexAdapter)

MAX_POST_BYTES = 4096
REQUEST_IDLE_TIMEOUT_SECONDS = 5.0


class NativeHTTPServer(HTTPServer):
    """Bound idle client sockets so one stalled request cannot hold the worker.

    The native Development listener is intentionally single-worker, enforcing
    a service-wide fusion request budget of one. Without an accept-time socket
    deadline, a client could occupy that worker indefinitely before finishing
    headers or a declared JSON request body.
    """

    request_idle_timeout_seconds = REQUEST_IDLE_TIMEOUT_SECONDS

    def get_request(self):
        connection, client = super().get_request()
        connection.settimeout(self.request_idle_timeout_seconds)
        return connection, client


def make_handler(index: SearchIndex, *, fusion_providers: Sequence[ProviderBinding] = (),
                 allow_synthetic_fixtures: bool = False):
    if not isinstance(fusion_providers, (list, tuple)) or type(allow_synthetic_fixtures) is not bool:
        raise ValueError('Invalid fusion service configuration')
    if len(fusion_providers) > 7 or any(
            not isinstance(binding, ProviderBinding)
            or binding.source == OWNED_INDEX_SOURCE for binding in fusion_providers):
        raise ValueError('Invalid or reserved fusion source configuration')
    # An actual FTS index is always part of the Web category. It never makes
    # a network call, so it does not require a fictional upstream contract.
    owned = ProviderBinding(OWNED_INDEX_SOURCE, OwnedIndexAdapter(index), ProviderRights(
        frozenset({'web'}), True, True, True,
        OWNED_INDEX_EVIDENCE, 'owned_index'))
    external_providers = tuple(fusion_providers)
    web_providers = (owned,) + external_providers

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
            if self.path == '/v1/fusion':
                return self.respond(405, {'error': 'Fusion requires JSON POST'})
            return self.respond(404, {'error': 'Not found'})

        def do_OPTIONS(self):
            # A loopback native process is not a cross-origin web service.
            if not self.authorized_host():
                return self.respond(403, {'error': 'Host is not a loopback listener'})
            return self.respond(405, {'error': 'Cross-origin requests are disabled'})

        def do_POST(self):
            if not self.authorized_host():
                return self.respond(403, {'error': 'Host is not a loopback listener'})
            if self.path not in ('/v1/search', '/v1/fusion'):
                return self.respond(404 if '?' not in self.path else 405, {'error': 'Unknown endpoint'})
            if 'Origin' in self.headers:
                return self.respond(403, {'error': 'Browser-origin submissions are not enabled'})
            if 'Transfer-Encoding' in self.headers:
                return self.respond(422, {'error': 'Chunked request bodies are not enabled'})
            if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                return self.respond(415, {'error': 'JSON content type required'})
            try:
                length = int(self.headers.get('Content-Length', '-1'))
                if not 1 <= length <= MAX_POST_BYTES:
                    raise ValueError()
                data = self.rfile.read(length)
                supplied = json.loads(data)
                if not isinstance(supplied, dict):
                    raise ValueError()
                if self.path == '/v1/fusion':
                    if set(supplied) - {'query', 'category', 'limit'}:
                        raise ValueError()
                    category = supplied.get('category', 'web')
                    providers = web_providers if category == 'web' else external_providers
                    if category == 'web':
                        # The local FTS search budget is intentionally tighter
                        # than the general third-party dispatch contract.
                        clean_query(supplied.get('query'))
                    if not providers:
                        return self.respond(503, {'error': 'No fusion providers for this category'})
                    reply = asyncio.run(dispatch_fusion(
                        supplied.get('query'), category=category,
                        providers=providers, limit=supplied.get('limit', 20),
                        allow_synthetic_fixtures=allow_synthetic_fixtures))
                    return self.respond(200, {
                        'schema_version': reply.schema_version,
                        'mode': ('synthetic_fixture_preview' if allow_synthetic_fixtures
                                 else 'owned_index_only' if not external_providers
                                 else 'owned_index_with_configured_providers'),
                        'category': reply.category,
                        'status': reply.status,
                        'total_displayed': len(reply.results),
                        'providers': [asdict(outcome) for outcome in reply.providers],
                        'results': [asdict(card) for card in reply.results],
                    })
                if set(supplied) - {'query', 'limit'}:
                    raise ValueError()
                hits = index.search(supplied.get('query'), limit=supplied.get('limit', 10))
            except TimeoutError:
                return self.respond(408, {'error': 'Request body timed out'})
            except (ValueError, UnicodeError, TypeError, json.JSONDecodeError):
                return self.respond(422, {'error': 'Invalid bounded search request'})
            return self.respond(200, {
                'source': 'goreecloud-native-index',
                'total_displayed': len(hits),
                'results': [asdict(h) for h in hits],
            })
    return NativeHandler


def run_loopback(index: SearchIndex, *, port: int = 8789,
                 fusion_providers: Sequence[ProviderBinding] = (),
                 allow_synthetic_fixtures: bool = False) -> None:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Choose a nonprivileged loopback port')
    server = NativeHTTPServer(('127.0.0.1', port), make_handler(
        index, fusion_providers=fusion_providers,
        allow_synthetic_fixtures=allow_synthetic_fixtures))
    try:
        print('Native Search development API: http://127.0.0.1:%d' % port)
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
