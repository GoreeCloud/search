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
LEGACY_SOURCES = ('brave', 'startpage', 'qwant')
SOURCES = LEGACY_SOURCES + ('duckduckgo', 'ecosia', 'bing', 'google')
# Keep these identifiers aligned with the approved per-category engine registry.
# Standalone CLI must not need to load the running Search application.
CATEGORY_ENGINES = {
    'general': {family: family for family in SOURCES},
    'images': {'brave': 'brave.images', 'startpage': 'startpage images',
               'qwant': 'qwant images', 'duckduckgo': 'duckduckgo images',
               'bing': 'bing images', 'google': 'google images'},
    'videos': {'brave': 'brave.videos', 'qwant': 'qwant videos',
               'duckduckgo': 'duckduckgo videos', 'bing': 'bing videos',
               'google': 'google videos'},
    'news': {'brave': 'brave.news', 'startpage': 'startpage news',
             'qwant': 'qwant news', 'duckduckgo': 'duckduckgo news',
             'bing': 'bing news', 'google': 'google news'},
}
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


def classify_provider_error(message: str) -> str:
    """Return a bounded diagnostic category; never echo upstream error details."""
    text = message.lower()
    if 'timeout' in text or 'timed out' in text:
        return 'timeout'
    if '429' in text or 'too many requests' in text or 'toomanyrequests' in text or 'rate limit' in text:
        return 'rate_limited'
    if 'captcha' in text or 'challenge' in text:
        return 'challenge'
    if '403' in text or 'access denied' in text or 'accessdenied' in text or 'blocked' in text:
        return 'access_denied'
    # SearXNG translates several different HTTP statuses to a generic
    # 'HTTP error'. Do not claim 403 or 429 unless that status is visible.
    if 'http error' in text or 'http status' in text:
        return 'upstream_http_error'
    if 'server api error' in text:
        return 'upstream_api_error'
    if 'unexpected crash' in text:
        return 'engine_error'
    if 'pars' in text or 'markup' in text:
        return 'parsing_error'
    if 'proxy' in text or 'connection' in text or 'network' in text:
        return 'network_error'
    return 'other_error'


def probe(source: str, origin: str, *, category: str = 'general',
          transport=None, timeout: float = 30.0) -> dict:
    """Send a fixed synthetic query to one approved category/source adapter."""
    if category not in CATEGORY_ENGINES or source not in CATEGORY_ENGINES[category]:
        raise ValueError('Unsupported provider/category combination')
    engine = CATEGORY_ENGINES[category][source]
    base = require_private_origin(origin)
    fields = {'q': QUERY, 'engines': engine, 'format': 'json'}
    if category != 'general':
        fields['category_' + category] = '1'
    payload = urlencode(fields).encode('ascii')
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
        if metadata.get('selected_engines') != [engine]:
            return {'provider': source, 'state': 'selection_mismatch'}
        errors = doc.get('unresponsive_engines')
        if not isinstance(errors, list):
            return {'provider': source, 'state': 'invalid_error_contract'}
        types = set()
        for error in errors:
            if (not isinstance(error, (list, tuple)) or len(error) < 2
                    or error[0] != engine or not isinstance(error[1], str)):
                # Do not trust malformed or other-provider error attribution.
                return {'provider': source, 'state': 'invalid_error_contract'}
            types.add(classify_provider_error(error[1]))
        results = doc.get('results')
        if not isinstance(results, list):
            return {'provider': source, 'state': 'invalid_result_contract'}
        state = ('partial_results' if errors and results else
                 'provider_error' if errors else
                 'results_observed' if results else 'no_results')
        return {'provider': source, 'state': state,
                'result_count': len(results), 'error_count': len(errors),
                'error_categories': sorted(types)}
    except (OSError, ValueError, TypeError) as exc:
        # Never expose exception text; error URLs may contain the query.
        return {'provider': source, 'state': 'request_or_decode_error',
                'error_type': type(exc).__name__}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8888')
    # Keep 'both' as the legacy three-provider sweep; require explicit 'all'
    # for the expanded seven-provider diagnostic to avoid new implicit egress.
    parser.add_argument('--provider', choices=(*SOURCES, 'both', 'all'), default='both')
    parser.add_argument('--category', choices=tuple(CATEGORY_ENGINES), default='general',
                        help='Search category; non-Web probes require explicit selection')
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
    approved = CATEGORY_ENGINES[args.category]
    selected = (LEGACY_SOURCES if args.provider == 'both' else
                tuple(family for family in SOURCES if family in approved)
                if args.provider == 'all' else (args.provider,))
    if any(source not in approved for source in selected):
        parser.error('Provider is not approved in this category; choose a supported provider or all')
    outcomes = ([probe(source, args.url) for source in selected] if args.category == 'general'
                else [probe(source, args.url, category=args.category) for source in selected])
    print(json.dumps({'development_only': True, 'category': args.category,
                      'results': outcomes}, sort_keys=True))
    return 0 if all(item['state'] == 'results_observed' for item in outcomes) else 1


if __name__ == '__main__':
    sys.exit(main())
