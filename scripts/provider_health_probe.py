#!/usr/bin/env python3
"""Opt-in live-provider diagnostic for an already running local *development* Search.

Run only from a controlled workstation with the private Search instance bound to
loopback, after explicitly agreeing to transmit a fixed synthetic query. Never
run against production. Prints neither search terms nor provider results.
"""
from __future__ import annotations

import argparse
import json
import sys
from unicodedata import category
from urllib.parse import urlsplit, urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

QUERY = 'goreecloud synthetic provider verification'
SOURCES = ('brave', 'startpage', 'qwant')
MAX_BYTES = 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    """Never forward a POST to any redirected destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def private_transport(request, *, timeout):
    """Ignore environment proxy settings and refuse HTTP redirects."""
    return build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout)


def require_private_origin(raw: str) -> str:
    """Pin localhost to numeric loopback; fail closed on URL normalization."""
    if (not isinstance(raw, str) or not raw or raw != raw.strip()
            or any(ord(ch) < 33 or ord(ch) == 127
                   or category(ch) in ('Cc', 'Cf', 'Cs') for ch in raw)):
        raise ValueError('Invalid local service URL')
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Invalid local service URL') from exc
    if (parsed.scheme != 'http'
            or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')
            or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or '?' in raw or '#' in raw or port == 0):
        raise ValueError('Only an HTTP loopback base URL without credentials, path or query is accepted')
    host = ('[::1]' if parsed.hostname == '::1' else '127.0.0.1')
    return 'http://' + host + ((':' + str(port)) if port is not None else '')


def probe(source: str, origin: str, *, transport=None, timeout: float = 30.0) -> dict:
    """Send synthetic terms to exactly one source and return aggregate state."""
    if source not in SOURCES:
        raise ValueError('Unsupported provider')
    base = require_private_origin(origin)
    payload = urlencode({'q': QUERY, 'engines': source, 'format': 'json'}).encode('ascii')
    request = Request(base + '/search', data=payload, method='POST', headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    })
    try:
        with (transport or private_transport)(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return {'provider': source, 'state': 'response_too_large'}
        doc = json.loads(raw)
        if not isinstance(doc, dict):
            return {'provider': source, 'state': 'invalid_response_contract'}
        metadata = doc.get('goreecloud')
        if not isinstance(metadata, dict):
            return {'provider': source, 'state': 'invalid_response_contract'}
        if metadata.get('selected_engines') != [source]:
            return {'provider': source, 'state': 'selection_mismatch'}
        errors = doc.get('unresponsive_engines')
        if not isinstance(errors, list):
            return {'provider': source, 'state': 'invalid_error_contract'}
        results = doc.get('results')
        if not isinstance(results, list):
            return {'provider': source, 'state': 'invalid_result_contract'}
        state = ('provider_error' if errors else
                 'results_observed' if results else 'no_results')
        return {'provider': source, 'state': state,
                'result_count': len(results), 'error_count': len(errors)}
    except (OSError, ValueError, TypeError) as exc:
        # Never expose exception text; error URLs may contain the query.
        return {'provider': source, 'state': 'request_or_decode_error',
                'error_type': type(exc).__name__}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8888')
    parser.add_argument('--provider', choices=(*SOURCES, 'both'), default='both')
    parser.add_argument('--allow-provider-egress', action='store_true',
                        help='Send fixed synthetic terms to selected provider(s)')
    args = parser.parse_args(argv)
    try:
        require_private_origin(args.url)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.allow_provider_egress:
        print('No requests sent. Re-run with --allow-provider-egress for a loopback Development instance.')
        return 64
    selected = SOURCES if args.provider == 'both' else (args.provider,)
    outcomes = [probe(source, args.url) for source in selected]
    print(json.dumps({'development_only': True, 'results': outcomes}, sort_keys=True))
    return 0 if all(item['state'] == 'results_observed' for item in outcomes) else 1


if __name__ == '__main__':
    sys.exit(main())
