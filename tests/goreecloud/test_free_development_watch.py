"""Offline fail-closed contracts for the owner-only Search deployment audit."""
import importlib.util
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('free_development_watch',
                                            ROOT / 'scripts/free_development_watch.py')
watch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watch)
REV = '40caeb47a1fd8fc15a60f54e5e383d1a9f280598'


class FakeResponse:
    def __init__(self, body, status=200):
        self.payload = body if isinstance(body, bytes) else body.encode()
        self.status = status

    def read(self, length=-1):
        return self.payload[:length] if length != -1 else self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, *, modified=None):
        self.requests = []
        self.modified = modified or {}

    def open(self, req, timeout):
        self.requests.append(req)
        path = urlsplit(req.full_url).path
        if path in self.modified:
            value = self.modified[path]
            if isinstance(value, Exception):
                raise value
            return value
        if path == '/readyz':
            return FakeResponse(b'READY\n')
        if path == '/':
            return FakeResponse(
                b'<html><head><meta name="generator" content="searxng/2026.10.20+40caeb47a1f">'
                b'</head><body>Free metasearch</body></html>'
            )
        if path == '/preferences':
            return FakeResponse(
                b'<input type="radio" name="goreecloud_sources" value="working" checked>'
                b'<input type="radio" name="goreecloud_sources" value="all">'
            )
        if path == '/search':
            data = parse_qs(req.data.decode())
            cat = next((key[9:] for key in data if key.startswith('category_')), 'general')
            engine_set = {c[0]: list(c[2]) for c in watch.CASES}[cat]
            return FakeResponse(json.dumps({
                'goreecloud': {'selected_engines': engine_set},
                'results': [{'url': 'https://example.org'}],
                'unresponsive_engines': [],
            }))
        raise AssertionError('out-of-scope path')


def execute(args, opener):
    with patch('sys.stdout', new_callable=StringIO) as output:
        code = watch.main(args, opener=opener)
        report = json.loads(output.getvalue())
        return code, report, output.getvalue()


class FreeDevelopmentWatchTests(unittest.TestCase):
    def test_default_is_three_no_query_https_requests(self):
        opener = FakeOpener()
        code, report, serialized = execute(['--expected-revision', REV], opener)
        self.assertEqual(0, code)
        self.assertEqual('pass', report['status'])
        self.assertEqual('no_provider_queries', report['mode'])
        self.assertEqual(0, report['provider_requests_attempted'])
        self.assertEqual(3, len(opener.requests))
        self.assertEqual(['/readyz', '/', '/preferences'],
                         [urlsplit(req.full_url).path for req in opener.requests])
        self.assertTrue(all(req.full_url.startswith('https://search-dev.goreecloud.com/')
                            and req.get_method() == 'GET' and req.data is None
                            for req in opener.requests))
        self.assertNotIn('public library', serialized)

    def test_wrong_build_or_source_preference_fails_closed(self):
        old = FakeOpener(modified={'/': FakeResponse(
            '<meta name="generator" content="searxng/2026.10.20+64c4cab8e2">')})
        code, doc, _ = execute(['--expected-revision', REV], old)
        self.assertEqual(2, code)
        self.assertEqual('fail', doc['status'])
        self.assertEqual('unexpected_response', doc['checks'][1]['reason'])
        bad = FakeOpener(modified={'/preferences': FakeResponse(
            '<input name="goreecloud_sources" value="all" checked>')})
        code, doc, _ = execute(['--expected-revision', REV], bad)
        self.assertEqual(2, code)
        self.assertFalse(doc['checks'][2]['passed'])

    def test_shadowed_source_controls_cannot_spoof_a_healthy_default(self):
        examples = (
            '<input name="goreecloud_sources" value="working" checked>'
            '<input name="goreecloud_sources" value="all">',
            '<input type="hidden" name="goreecloud_sources" value="working" checked>'
            '<input type="radio" name="goreecloud_sources" value="all">',
            '<input type="radio" name="goreecloud_sources" value="working" checked>'
            '<input type="radio" name="goreecloud_sources" value="working">'
            '<input type="radio" name="goreecloud_sources" value="all">',
        )
        for markup in examples:
            with self.subTest(markup=markup):
                opener = FakeOpener(modified={'/preferences': FakeResponse(markup)})
                code, report, _ = execute(['--expected-revision', REV], opener)
                self.assertEqual(2, code)
                self.assertFalse(report['checks'][2]['passed'])

    def test_redirect_error_does_not_reach_external_host_or_log_url(self):
        failure = HTTPError('https://search-dev.goreecloud.com/readyz',
                            302, 'Moved to secret.example', {}, None)
        opener = FakeOpener(modified={'/readyz': failure})
        code, doc, serial = execute(['--expected-revision', REV], opener)
        self.assertEqual(2, code)
        self.assertEqual('http_denied', doc['checks'][0]['reason'])
        self.assertNotIn('secret.example', serial)
        self.assertEqual(3, len(opener.requests))
        self.assertIsNone(watch.NoRedirect().redirect_request(None, None, 301,
                                                               'Moved', {}, 'https://example.org'))

    def test_bounded_source_check_is_explicit_and_not_silently_substituted(self):
        opener = FakeOpener()
        code, report, out = execute(['--expected-revision', REV, '--check-sources'],
                                    opener)
        self.assertEqual(0, code)
        self.assertEqual('synthetic_opt_in', report['mode'])
        self.assertEqual(4, report['provider_requests_attempted'])
        self.assertEqual(7, len(opener.requests))
        self.assertEqual(4, sum(req.get_method() == 'POST' for req in opener.requests))
        for req, (cat, phrase, engines) in zip(opener.requests[3:], watch.CASES):
            fields = parse_qs(req.data.decode())
            self.assertIn('category_' + cat, fields)
            self.assertEqual(phrase, fields['q'][0])
            self.assertNotIn('engines', fields)
            self.assertNotIn(phrase, out)
            self.assertEqual('https://search-dev.goreecloud.com', req.headers['Origin'])
        self.assertTrue(all(c['passed'] for c in report['checks']))

    def test_core_failure_must_not_emit_provider_queries(self):
        opener = FakeOpener(modified={'/': FakeResponse('broken')})
        code, report, _ = execute(['--expected-revision', REV, '--check-sources'],
                                  opener)
        self.assertEqual(2, code)
        self.assertEqual('fail', report['status'])
        self.assertEqual(3, len(opener.requests))
        self.assertEqual(0, report['provider_requests_attempted'])

    def test_403_aborts_remaining_source_probes_without_retry(self):
        deny = HTTPError('https://search-dev.goreecloud.com/search', 403,
                         'Forbidden', {}, None)
        opener = FakeOpener(modified={'/search': deny})
        code, report, out = execute(['--expected-revision', REV, '--check-sources'],
                                    opener)
        self.assertEqual(2, code)
        self.assertEqual(4, len(opener.requests))
        self.assertEqual(1, report['provider_requests_attempted'])
        self.assertEqual('http_denied', report['checks'][-1]['reason'])
        self.assertNotIn('Forbidden', out)

    def test_reject_source_mismatch_partial_and_empty(self):
        for case in (
            {'goreecloud': {'selected_engines': ['google']}, 'results': [{}],
             'unresponsive_engines': []},
            {'goreecloud': {'selected_engines': ['bing','duckduckgo','startpage']},
             'results': [{}], 'unresponsive_engines': [['bing', 'blocked']]},
            {'goreecloud': {'selected_engines': ['bing','duckduckgo','startpage']},
             'results': [], 'unresponsive_engines': []},
        ):
            with self.subTest(case=case):
                opener = FakeOpener(modified={'/search': FakeResponse(json.dumps(case))})
                code, report, out = execute(
                    ['--expected-revision', REV, '--check-sources'], opener)
                self.assertEqual(2, code)
                self.assertFalse(report['checks'][3]['passed'])
                self.assertNotIn('blocked', out)

    def test_reports_only_allowlisted_failing_engine_names(self):
        case = {
            'goreecloud': {'selected_engines': ['bing','duckduckgo','startpage']},
            'results': [{}],
            'unresponsive_engines': [['startpage', 'access denied at https://secret.example/private']],
        }
        opener = FakeOpener(modified={'/search': FakeResponse(json.dumps(case))})
        code, report, output = execute(['--expected-revision', REV, '--check-sources'], opener)
        self.assertEqual(2, code)
        self.assertEqual(['startpage'], report['checks'][3]['failed_engines'])
        self.assertNotIn('secret.example', output)
        case['unresponsive_engines'] = [['https://evil.example/private', 'blocked']]
        code, report, output = execute(['--expected-revision', REV, '--check-sources'],
                                       FakeOpener(modified={'/search': FakeResponse(json.dumps(case))}))
        self.assertEqual(2, code)
        self.assertEqual([], report['checks'][3]['failed_engines'])
        self.assertEqual('invalid_error_attribution', report['checks'][3]['reason'])
        self.assertNotIn('evil.example', output)

    def test_reject_oversized_payload_invalid_args_and_arbitrary_paths(self):
        opener = FakeOpener(modified={'/': FakeResponse(b'x' * (watch.MAX_HTML_BYTES + 1))})
        self.assertEqual(2, execute(['--expected-revision', REV], opener)[0])
        with self.assertRaises(ValueError):
            watch.fetch(FakeOpener(), '/favicon.ico')
        with self.assertRaises(ValueError):
            watch.fetch(FakeOpener(), '/search')
        for args in (['--expected-revision', 'bad'],
                     ['--expected-revision', REV, '--timeout', '0.1']):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                watch.main(args, opener=FakeOpener())

    def test_default_https_context_keeps_verification_and_ignores_proxies(self):
        transport = watch.locked_down_opener()
        handler_names = [type(h).__name__ for h in transport.handlers]
        self.assertIn('HTTPSHandler', handler_names)
        self.assertIn('NoRedirect', handler_names)
        self.assertFalse(any(type(h).__name__ == 'ProxyHandler' and h.proxies
                             for h in transport.handlers))



class GeneratorMarkupTests(unittest.TestCase):
    def test_attribute_order_quote_style_and_duplicate_meta(self):
        for document in (
            "<META content='searxng/2026.10.20+40caeb47a1f' name='generator'>",
            '<meta data-extra="true" name="generator" content="searxng/2026.10.20+40caeb47a1f">',
        ):
            with self.subTest(document=document):
                parser = watch.GeneratorParser()
                parser.feed(document)
                self.assertTrue(parser.matches(REV))
        for document in (
            '<meta name="generator" content="searxng/2026.10.20+64c4cab8e2">',
            '<meta name="generator" content="searxng/2026.10.20+40caeb47a1f">'
            '<meta name="generator" content="searxng/2026.10.20+40caeb47a1f">',
            '<script><meta name="generator" content="searxng/2026.10.20+40caeb47a1f"></script>',
        ):
            with self.subTest(document=document):
                parser = watch.GeneratorParser()
                parser.feed(document)
                self.assertFalse(parser.matches(REV))


if __name__ == '__main__':
    unittest.main()
