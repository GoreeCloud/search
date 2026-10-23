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


def synthetic_document(expected, results=None, errors=None):
    if results is None:
        results = [{'url': 'https://example.org', 'title': 'Public resource',
                    'engine': expected[0], 'engines': [expected[0]]}]
    counts = {}
    for hit in results:
        if isinstance(hit, dict):
            for name in set([hit.get('engine'), *(hit.get('engines') or [])]):
                if isinstance(name, str) and name in expected:
                    counts[name] = counts.get(name, 0) + 1
    counts = dict(sorted(counts.items()))
    return {
        'goreecloud': {
            'selected_engines': list(expected),
            'selected_engine_count': len(expected),
            'selection_not_contact_confirmation': True,
            'represented_engines': list(counts),
            'represented_result_counts': counts,
            'representation_not_contact_confirmation': True,
        },
        'results': results,
        'unresponsive_engines': errors if errors is not None else [],
    }


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
            return value(req) if callable(value) else value
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
            return FakeResponse(json.dumps(synthetic_document(engine_set)))
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

    def test_duplicated_html_attributes_never_attest_release_or_defaults(self):
        valid_revision = 'searxng/2026.10.20+40caeb47a1f'
        for html in (
            '<meta name="other" name="generator" content="'+valid_revision+'">',
            '<meta name="generator" content="incorrect" content="'+valid_revision+'">',
        ):
            with self.subTest(page='homepage', html=html):
                code, report, _ = execute(['--expected-revision', REV],
                                          FakeOpener(modified={'/': FakeResponse(html)}))
                self.assertEqual(2, code)
                self.assertFalse(report['checks'][1]['passed'])
                self.assertEqual(0, report['provider_requests_attempted'])
        for html in (
            '<input type="hidden" type="radio" name="goreecloud_sources" '
            'value="working" checked>',
            '<input type="radio" name="other" name="goreecloud_sources" '
            'value="working" checked>',
            '<input type="radio" name="goreecloud_sources" '
            'value="all" value="working" checked>',
        ):
            markup = html + '<input type="radio" name="goreecloud_sources" value="all">'
            with self.subTest(page='preferences', html=html):
                code, report, _ = execute(['--expected-revision', REV],
                                          FakeOpener(modified={'/preferences': FakeResponse(markup)}))
                self.assertEqual(2, code)
                self.assertFalse(report['checks'][2]['passed'])
                self.assertEqual(0, report['provider_requests_attempted'])

    def test_inert_template_generator_cannot_attest_image_revision(self):
        valid_revision = 'searxng/2026.10.20+40caeb47a1f'
        for markup in (
            '<template><meta name="generator" content="'+valid_revision+'"></template>',
            '<template><template><meta name="generator" content="'+valid_revision
            +'"></template></template>',
        ):
            with self.subTest(markup=markup):
                code, report, _ = execute(
                    ['--expected-revision', REV, '--check-sources'],
                    FakeOpener(modified={'/': FakeResponse(markup)}),
                )
                self.assertEqual(2, code)
                self.assertFalse(report['checks'][1]['passed'])
                self.assertEqual(0, report['provider_requests_attempted'])
        # A real head meta remains authoritative even when sample component
        # markup contains a conflicting, non-rendered generator tag.
        markup = ('<head><meta name="generator" content="'+valid_revision+'"></head>'
                  '<template><meta name="generator" content="stale"></template>')
        code, report, _ = execute(
            ['--expected-revision', REV],
            FakeOpener(modified={'/': FakeResponse(markup)}),
        )
        self.assertEqual(0, code)
        self.assertTrue(report['checks'][1]['passed'])

    def test_disabled_source_controls_are_not_usable_preferences(self):
        for html in (
            '<input type="radio" name="goreecloud_sources" value="working" checked disabled>'
            '<input type="radio" name="goreecloud_sources" value="all">',
            '<input type="radio" name="goreecloud_sources" value="working" checked>'
            '<input type="radio" name="goreecloud_sources" value="all" disabled>',
            '<fieldset disabled>'
            '<input type="radio" name="goreecloud_sources" value="working" checked>'
            '<input type="radio" name="goreecloud_sources" value="all">'
            '</fieldset>',
            '<fieldset disabled><fieldset>'
            '<input type="radio" name="goreecloud_sources" value="working" checked>'
            '<input type="radio" name="goreecloud_sources" value="all">'
            '</fieldset></fieldset>',
        ):
            with self.subTest(html=html):
                opener = FakeOpener(modified={'/preferences': FakeResponse(html)})
                code, result, _ = execute(['--expected-revision', REV], opener)
                self.assertEqual(code, 2)
                self.assertFalse(result['checks'][2]['passed'])
                self.assertEqual(0, result['provider_requests_attempted'])

    def test_inert_template_controls_cannot_fake_a_live_source_preference(self):
        markup = ('<template><input type="radio" name="goreecloud_sources" '
                  'value="working" checked>'
                  '<input type="radio" name="goreecloud_sources" value="all">'
                  '</template>')
        code, report, _ = execute(['--expected-revision', REV],
                                  FakeOpener(modified={'/preferences': FakeResponse(markup)}))
        self.assertEqual(2, code)
        self.assertFalse(report['checks'][2]['passed'])
        self.assertEqual(0, report['provider_requests_attempted'])

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

    def test_http_200_with_provider_failure_aborts_later_probes(self):
        # SearXNG may report a provider-side block or throttle in a 200 JSON
        # response. DuckDuckGo is selected in multiple later categories, so
        # the monitor must not continue probing after this first failure.
        expected = watch.CASES[0][2]
        response = synthetic_document(
            expected,
            errors=[['duckduckgo', '429 at https://private.example/path']],
        )
        opener = FakeOpener(modified={'/search': FakeResponse(json.dumps(response))})
        code, report, output = execute(
            ['--expected-revision', REV, '--check-sources'], opener,
        )
        self.assertEqual(2, code)
        self.assertEqual(1, report['provider_requests_attempted'])
        self.assertEqual(4, len(opener.requests))
        self.assertEqual(['synthetic_general'],
                         [item['check'] for item in report['checks'][3:]])
        self.assertEqual(['duckduckgo'], report['checks'][-1]['failed_engines'])
        self.assertNotIn('private.example', output)

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

    def test_rejects_result_placeholders_and_unsafe_links_without_echoing_them(self):
        invalid_results = (
            {},
            {'url': 'https://public.example.org', 'title': ''},
            {'url': 'javascript:alert(1)', 'title': 'Unsafe'},
            {'url': 'https://127.0.0.1/internal', 'title': 'Private'},
            {'url': 'http://2130706433/secrets', 'title': 'Private numeric host'},
            {'url': 'https://user:secret@public.example.org/', 'title': 'Credentials'},
            {'url': 'https://public.example.org/\nprivate', 'title': 'Control character'},
            {'url': 'https://public.example.org', 'title': None},
        )
        for hit in invalid_results:
            with self.subTest(hit=hit):
                payload = {'goreecloud': {'selected_engines': list(watch.CASES[0][2])},
                           'results': [hit], 'unresponsive_engines': []}
                code, report, output = execute(
                    ['--expected-revision', REV, '--check-sources'],
                    FakeOpener(modified={'/search': FakeResponse(json.dumps(payload))}))
                self.assertEqual(2, code)
                self.assertEqual(0, report['checks'][3]['result_count'])
                self.assertFalse(report['checks'][3]['passed'])
                self.assertNotIn('secret', output)
                self.assertNotIn('javascript:', output)

    def test_valid_links_are_counted_without_storing_raw_provider_results(self):
        def results_for_request(req, *, invalid=False):
            fields = parse_qs(req.data.decode())
            cat = next(key[9:] for key in fields if key.startswith('category_'))
            expected = next(engines for category, _, engines in watch.CASES
                            if category == cat)
            hits = [{'url': 'https://public.example.org/guide', 'title': 'Guide',
                     'engine': expected[0], 'engines': [expected[0]]}]
            if invalid:
                hits.append({'url': 'https://127.0.0.1/admin', 'title': 'Private',
                             'engine': expected[0], 'engines': [expected[0]]})
            payload = synthetic_document(expected, results=hits)
            return FakeResponse(json.dumps(payload))
        code, report, output = execute(
            ['--expected-revision', REV, '--check-sources'],
            FakeOpener(modified={'/search': results_for_request}))
        self.assertEqual(0, code)
        self.assertTrue(all(item['result_count'] == 1 for item in report['checks'][3:]))
        self.assertNotIn('public.example.org', output)
        code, report, output = execute(
            ['--expected-revision', REV, '--check-sources'],
            FakeOpener(modified={'/search': lambda req: results_for_request(req, invalid=True)}))
        self.assertEqual(2, code)
        self.assertTrue(all(item['result_count'] == 0 for item in report['checks'][3:]))
        self.assertTrue(all(item['reason'] == 'invalid_result_attribution'
                            for item in report['checks'][3:]))
        self.assertNotIn('127.0.0.1', output)

    def test_misattributed_results_and_forged_counts_never_pass(self):
        expected = watch.CASES[0][2]
        valid = {'url': 'https://public.example.org', 'title': 'Public',
                 'engine': expected[0], 'engines': [expected[0]]}
        cases = (
            synthetic_document(expected, results=[{**valid, 'engine': 'google',
                                                   'engines': ['google']}]),
            synthetic_document(expected, results=[{**valid, 'engines': ['google', expected[0]]}]),
            synthetic_document(expected, results=[{**valid, 'engine': None}]),
            synthetic_document(expected, results=[{**valid, 'engines': []}]),
        )
        forged = synthetic_document(expected, results=[valid])
        forged['goreecloud']['represented_result_counts'][expected[0]] = 2
        cases += (forged,)
        forged = synthetic_document(expected, results=[valid])
        forged['goreecloud']['selection_not_contact_confirmation'] = False
        cases += (forged,)
        for payload in cases:
            with self.subTest(payload=payload):
                code, report, output = execute(
                    ['--expected-revision', REV, '--check-sources'],
                    FakeOpener(modified={'/search': FakeResponse(json.dumps(payload))}))
                self.assertEqual(2, code)
                self.assertEqual(0, report['checks'][3]['result_count'])
                self.assertEqual('invalid_result_attribution', report['checks'][3]['reason'])
                self.assertNotIn('public.example.org', output)

    def test_merged_result_attribution_is_counted_once_per_visible_link(self):
        expected = watch.CASES[0][2]
        shared = {'url': 'https://example.org/merged', 'title': 'Merged',
                  'engine': expected[0], 'engines': [expected[0], expected[1]]}
        doc = synthetic_document(expected, results=[shared])
        self.assertEqual(1, watch.attributed_result_count([shared], expected, doc['goreecloud']))
        self.assertEqual({expected[0]:1, expected[1]:1},
                         doc['goreecloud']['represented_result_counts'])

    def test_boolean_source_counts_cannot_masquerade_as_one(self):
        expected = watch.CASES[3][2]  # News has one selected source.
        for location in ('selected_engine_count', 'represented_result_counts'):
            doc = synthetic_document(expected)
            if location == 'selected_engine_count':
                doc['goreecloud'][location] = True
            else:
                doc['goreecloud'][location][expected[0]] = True
            with self.subTest(location=location):
                self.assertIsNone(watch.attributed_result_count(
                    doc['results'], expected, doc['goreecloud']))

    def test_reports_only_allowlisted_failing_engine_names(self):
        case = synthetic_document(
            ('bing','duckduckgo','startpage'),
            errors=[['startpage', 'access denied at https://secret.example/private']])
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
