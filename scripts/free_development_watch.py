#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only, one-shot Development Search health audit from an authorized NetBird client.

No background process, scheduler, web crawling, query contents, tokens or personal
data. The default three GETs cannot initiate search-provider requests. Four fixed
synthetic category POSTs require explicit --check-sources; never retry denials.
"""
from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
from html.parser import HTMLParser
import json
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (HTTPCookieProcessor, HTTPRedirectHandler, HTTPSHandler,
                            ProxyHandler, Request, build_opener)

HOST = 'search-dev.goreecloud.com'
ORIGIN = 'https://' + HOST
REVISION = re.compile(r'^[0-9a-f]{40}$')
MAX_HTML_BYTES = 256 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
CASES = (
    ('general', 'public library open source catalog', ('bing', 'duckduckgo', 'startpage')),
    ('images', 'NASA public domain space telescope photographs', ('bing images',)),
    ('videos', 'NASA scientific mission documentary', ('bing videos', 'duckduckgo videos')),
    ('news', 'NASA Artemis program updates', ('duckduckgo news',)),
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class GeneratorParser(HTMLParser):
    """Identify exactly one generator meta tag regardless of attribute order."""
    def __init__(self):
        super().__init__()
        self.values = []
        self.ambiguous = False

    def handle_starttag(self, tag, attrs):
        if tag == 'meta':
            names = [key for key, _ in attrs]
            if names.count('name') > 1 or names.count('content') > 1:
                self.ambiguous = True
                return
            attributes = dict(attrs)
            name = attributes.get('name')
            if isinstance(name, str) and name.lower() == 'generator':
                content = attributes.get('content')
                self.values.append(content if isinstance(content, str) else '')

    def matches(self, expected_revision):
        if self.ambiguous or len(self.values) != 1:
            return False
        match = re.fullmatch(r'searxng/[^<>]*\+([0-9a-f]{10,12})', self.values[0])
        return match is not None and expected_revision.startswith(match.group(1))


class SourcePreferenceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.options = []
        self.checked = []
        self.disabled = []
        self.ambiguous = False

    def handle_starttag(self, tag, attrs):
        if tag != 'input':
            return
        names = [key for key, _ in attrs]
        if any(names.count(key) > 1 for key in ('name', 'type', 'value', 'checked', 'disabled')):
            self.ambiguous = True
            return
        item = dict(attrs)
        # Only radio controls represent a selectable preference. A hidden
        # or duplicate input must not make an unsafe default look healthy.
        if item.get('name') == 'goreecloud_sources' and item.get('type', '').lower() == 'radio':
            self.options.append(item.get('value'))
            if 'disabled' in item:
                self.disabled.append(item.get('value'))
            if 'checked' in item:
                self.checked.append(item.get('value'))


def locked_down_opener():
    """Do not trust environment proxies, follow redirects, or disable TLS verification."""
    return build_opener(
        ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()),
        HTTPCookieProcessor(CookieJar()), NoRedirect(),
    )


def fetch(opener, path: str, *, data: bytes | None = None,
          timeout: float = 10, max_bytes: int = MAX_HTML_BYTES):
    # Fixed allowlist prevents a future accidental arbitrary-URL monitor.
    if path not in ('/readyz', '/', '/preferences', '/search'):
        raise ValueError('unsupported path')
    if (data is None and path == '/search') or (data is not None and path != '/search'):
        raise ValueError('search POST requires explicit synthetic mode')
    headers = {'Accept': 'application/json' if data is not None else 'text/html'}
    if data is not None:
        headers.update({'Content-Type': 'application/x-www-form-urlencoded',
                        'Origin': ORIGIN, 'Sec-Fetch-Site': 'same-origin'})
    req = Request(ORIGIN + path, data=data, method='POST' if data is not None else 'GET',
                  headers=headers)
    with opener.open(req, timeout=timeout) as response:
        status = response.status if hasattr(response, 'status') else response.getcode()
        body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        return status, None
    return status, body


def core_audit(opener, *, expected_revision: str, timeout: float) -> list[dict]:
    if not REVISION.fullmatch(expected_revision):
        raise ValueError('expected revision must be a full 40-character lowercase SHA')
    results = []
    for name, path in (('readiness', '/readyz'), ('homepage', '/'),
                       ('fresh_browser_source', '/preferences')):
        try:
            status, body = fetch(opener, path, timeout=timeout)
            if name == 'readiness':
                ok = status == 200 and body is not None and body.strip() == b'READY'
            elif name == 'homepage':
                parser = GeneratorParser()
                parser.feed((body or b'').decode('utf-8', errors='replace'))
                ok = status == 200 and parser.matches(expected_revision)
            else:
                parser = SourcePreferenceParser()
                parser.feed((body or b'').decode('utf-8', errors='replace'))
                ok = (status == 200 and parser.checked == ['working']
                      and parser.options.count('all') == 1
                      and parser.options.count('working') == 1
                      and not parser.disabled and not parser.ambiguous)
            results.append({'check': name, 'passed': bool(ok),
                            'reason': 'ok' if ok else 'unexpected_response'})
        except (HTTPError, URLError, OSError, ValueError, TypeError) as error:
            # Do not interpolate exception text: it may include a request URI.
            results.append({'check': name, 'passed': False,
                            'reason': ('http_denied' if isinstance(error, HTTPError) else
                                       type(error).__name__)})
    return results


def synthetic_category_audit(opener, *, timeout: float) -> list[dict]:
    """Exactly four synthetic requests with no retries or extra engine fallback."""
    results = []
    for category, query, expected in CASES:
        body = urlencode({
            'q': query, 'category_' + category: '1', 'format': 'json', 'language': 'en'
        }).encode('ascii')
        result = {'check': 'synthetic_' + category, 'passed': False, 'result_count': 0,
                  'provider_error_count': 0, 'failed_engines': [], 'reason': 'unexpected_response'}
        try:
            status, raw = fetch(opener, '/search', data=body,
                                timeout=timeout, max_bytes=MAX_JSON_BYTES)
            if status == 200 and raw is not None:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    metadata = parsed.get('goreecloud')
                    actual = metadata.get('selected_engines') if isinstance(metadata, dict) else None
                    hits = parsed.get('results')
                    errors = parsed.get('unresponsive_engines')
                    if (isinstance(actual, list) and all(isinstance(x, str) for x in actual)
                            and isinstance(hits, list) and isinstance(errors, list)):
                        result['result_count'] = len(hits)
                        result['provider_error_count'] = len(errors)
                        # Only display names that match explicitly configured
                        # free providers. Never echo upstream error messages.
                        recognized = all(
                            isinstance(err, (list, tuple)) and len(err) >= 2
                            and isinstance(err[0], str) and err[0] in expected
                            for err in errors
                        )
                        if recognized:
                            result['failed_engines'] = sorted({err[0] for err in errors})
                        result['passed'] = (sorted(actual) == sorted(expected)
                                            and len(hits) > 0 and not errors)
                        result['reason'] = ('ok' if result['passed'] else
                                            'invalid_error_attribution' if not recognized else
                                            'provider_or_selection_issue')
        except (HTTPError, URLError, OSError, ValueError, TypeError) as error:
            result['reason'] = 'http_denied' if isinstance(error, HTTPError) else type(error).__name__
            # A 403/429 is not a signal to attempt an alternative route.
            if isinstance(error, HTTPError) and error.code in (403, 429):
                results.append(result)
                break
        results.append(result)
    return results


def main(argv=None, *, opener=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-revision', required=True,
                        help='exact deployed image source revision (40 lowercase hex digits)')
    parser.add_argument('--timeout', type=float, default=10.0)
    parser.add_argument('--check-sources', action='store_true',
                        help='send exactly four public, synthetic source queries; opt-in only')
    args = parser.parse_args(argv)
    if not REVISION.fullmatch(args.expected_revision) or not 1 <= args.timeout <= 15:
        parser.error('supply exact 40-digit revision and timeout from 1 to 15 seconds')
    transport = opener or locked_down_opener()
    items = core_audit(transport, expected_revision=args.expected_revision,
                       timeout=args.timeout)
    submitted = 0
    if args.check_sources and all(item['passed'] for item in items):
        probes = synthetic_category_audit(transport, timeout=args.timeout)
        submitted = len(probes)
        items.extend(probes)
    report = {'environment': 'netbird_development', 'mode':
              'synthetic_opt_in' if args.check_sources else 'no_provider_queries',
              'provider_requests_attempted': submitted,
              'status': 'pass' if items and all(q['passed'] for q in items) else 'fail',
              'checks': items}
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'pass' else 2


if __name__ == '__main__':
    raise SystemExit(main())
