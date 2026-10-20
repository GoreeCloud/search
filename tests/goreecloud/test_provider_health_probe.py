"""Offline contracts for the opt-in, loopback-only provider health probe."""
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs
from unittest.mock import MagicMock, patch
import unittest

FILE = Path(__file__).resolve().parents[2] / 'scripts' / 'provider_health_probe.py'
spec = importlib.util.spec_from_file_location('provider_health_probe', FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ProviderProbeContractTests(unittest.TestCase):
    def test_remote_urls_and_query_urls_are_rejected(self):
        urls = (
            'https://127.0.0.1:8888', 'http://search.example:8888',
            'http://127.0.0.2:8888', 'http://localhost:8888/search',
            'http://localhost:8888/?q=private', 'http://localhost:8888?',
            'http://user:pass@localhost:8888', 'http://localhost:abc',
            'http://127.0.0.1:8888\n', 'http://localhost:8888\t',
        )
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                mod.require_private_origin(url)

    def test_localhost_pins_numeric_loopback(self):
        self.assertEqual('http://127.0.0.1:8888', mod.require_private_origin('http://localhost:8888'))
        self.assertEqual('http://[::1]:8888', mod.require_private_origin('http://[::1]:8888'))

    def test_fixed_post_and_provider_selection(self):
        seen = []
        def fake_transport(req, timeout):
            seen.append(req)
            return BytesIO(json.dumps({
                'goreecloud': {'selected_engines': ['brave'],
                               'represented_engines': ['brave'],
                               'represented_result_counts': {'brave': 1},
                               'representation_not_contact_confirmation': True},
                'results': [{'url': 'https://example.org', 'engine': 'brave', 'engines': ['brave']}],
                'unresponsive_engines': [],
            }).encode())
        result = mod.probe('brave', 'http://localhost:8888', transport=fake_transport)
        self.assertEqual('results_observed', result['state'])
        self.assertEqual('POST', seen[0].get_method())
        self.assertIn(b'engines=brave', seen[0].data)
        self.assertNotIn('verification', str(result))

    def test_qwant_is_checked_independently(self):
        captured = []
        def fake_transport(req, timeout):
            captured.append(req)
            return BytesIO(json.dumps({
                'goreecloud': {'selected_engines': ['qwant']},
                'results': [],
                'unresponsive_engines': [['qwant', 'blocked']],
            }).encode())
        outcome = mod.probe('qwant', 'http://127.0.0.1:8888', transport=fake_transport)
        self.assertEqual('provider_error', outcome['state'])
        self.assertEqual(1, outcome['error_count'])
        self.assertIn(b'engines=qwant', captured[0].data)
        self.assertNotIn('blocked', str(outcome))

    def test_malformed_json_shapes_fail_closed(self):
        for document in ([], 5, {'goreecloud': []}, {'goreecloud': None}):
            def fake_transport(req, timeout):
                return BytesIO(json.dumps(document).encode())
            with self.subTest(document=document):
                outcome = mod.probe('brave', 'http://localhost:8888', transport=fake_transport)
                self.assertEqual('invalid_response_contract', outcome['state'])

    def test_wrong_provider_response_is_rejected(self):
        def fake_transport(req, timeout):
            return BytesIO(json.dumps({
                'goreecloud': {'selected_engines': ['startpage']},
                'results': [], 'unresponsive_engines': [],
            }).encode())
        self.assertEqual('selection_mismatch', mod.probe(
            'brave', 'http://localhost:8888', transport=fake_transport)['state'])

    def test_results_require_selected_engine_and_public_safe_link(self):
        good_meta = {
            'selected_engines': ['brave'],
            'represented_engines': ['brave'],
            'represented_result_counts': {'brave': 1},
            'representation_not_contact_confirmation': True,
        }
        cases = (
            ({'url': 'https://example.org', 'engine': 'google', 'engines': ['google']},
             'invalid_result_attribution'),
            ({'url': 'https://example.org'}, 'invalid_result_attribution'),
            ({'url': 'https://example.org', 'engine': 'brave', 'engines': ['brave', 'google']},
             'invalid_result_attribution'),
            ({'url': 'javascript:alert(1)', 'engine': 'brave', 'engines': ['brave']},
             'invalid_result_contract'),
            ({'url': 'http://169.254.169.254/metadata', 'engine': 'brave', 'engines': ['brave']},
             'invalid_result_contract'),
            ({'url': 'https://user:pass@example.org', 'engine': 'brave', 'engines': ['brave']},
             'invalid_result_contract'),
        )
        for item, state in cases:
            with self.subTest(state=state, item=item):
                def fake_transport(req, timeout):
                    return BytesIO(json.dumps({
                        'goreecloud': good_meta, 'results': [item], 'unresponsive_engines': [],
                    }).encode())
                output = mod.probe('brave', 'http://127.0.0.1:8888', transport=fake_transport)
                self.assertEqual(state, output['state'])
                self.assertNotIn(str(item.get('url')), str(output))

    def test_mismatched_representation_count_cannot_report_success(self):
        def fake_transport(req, timeout):
            return BytesIO(json.dumps({
                'goreecloud': {'selected_engines': ['brave'],
                               'represented_engines': ['brave'],
                               'represented_result_counts': {'brave': 2},
                               'representation_not_contact_confirmation': True},
                'results': [{'url': 'https://example.org',
                             'engine': 'brave', 'engines': ['brave']}],
                'unresponsive_engines': [],
            }).encode())
        self.assertEqual('invalid_representation_contract', mod.probe(
            'brave', 'http://127.0.0.1:8888', transport=fake_transport)['state'])

    def test_nonpublic_hostname_aliases_and_numeric_ipv4_are_rejected(self):
        forbidden = (
            'http://localhost:8000/', 'http://service.local/',
            'https://metadata.google.internal/', 'https://host.lan/',
            'https://host.invalid/', 'https://host.test/',
            'https://host.onion/', 'https://host.arpa/',
            'http://localhost.localdomain/', 'https://host.home/',
            'https://host.corp/',
            'http://2130706433/', 'http://0177.0.0.1/',
            'http://0x7f000001/', 'http://127.1/',
            'https://singlelabel/', 'https://example.org./',
            'https://user:password@example.org/',
            'https://example.org:65536/',
            'https://[fe80::1%25eth0]/',
        )
        for url in forbidden:
            with self.subTest(url=url):
                self.assertFalse(mod.safe_reported_result_url(url))
        allowed = ('https://example.org/article',
                   'https://public.example.org/news?section=world',
                   'https://8.8.8.8/',
                   'https://[2606:4700:4700::1111]/')
        for url in allowed:
            with self.subTest(url=url):
                self.assertTrue(mod.safe_reported_result_url(url))

    def test_result_url_validator_performs_no_dns_or_network(self):
        with patch.object(mod, 'inet_aton', side_effect=OSError('not numeric')), \
                patch.object(mod, 'urlsplit', wraps=mod.urlsplit):
            self.assertTrue(mod.safe_reported_result_url('https://www.example.org/path'))

    def test_redirects_and_environment_proxies_are_disabled(self):
        req = mod.Request('http://127.0.0.1:8888/search', data=b'test', method='POST')
        opener = MagicMock()
        with patch.object(mod, 'build_opener', return_value=opener) as factory:
            mod.private_transport(req, timeout=2)
        self.assertEqual({}, factory.call_args.args[0].proxies)
        self.assertIsInstance(factory.call_args.args[1], mod._NoRedirect)
        self.assertIsNone(factory.call_args.args[1].redirect_request(
            req, None, 302, 'Found', {}, 'https://example.org/'))

    def test_default_does_not_send(self):
        with patch.object(mod, 'probe') as network, patch('builtins.print'):
            self.assertEqual(64, mod.main([]))
            network.assert_not_called()

    def test_expanded_provider_registry_and_no_egress_default(self):
        self.assertEqual(
            ('brave', 'startpage', 'qwant', 'duckduckgo', 'ecosia', 'bing', 'google'),
            mod.SOURCES,
        )
        with patch.object(mod, 'probe') as network, patch('builtins.print'):
            self.assertEqual(64, mod.main(['--provider', 'all']))
            network.assert_not_called()

    def test_explicit_all_probes_each_approved_family_only(self):
        def synthetic_outcome(source, origin):
            self.assertEqual('http://127.0.0.1:8888', origin)
            return {'provider': source, 'state': 'results_observed'}

        with patch.object(mod, 'probe', side_effect=synthetic_outcome) as network, \
                patch('builtins.print'):
            self.assertEqual(0, mod.main(['--provider', 'all', '--allow-provider-egress']))
        self.assertEqual(list(mod.SOURCES), [call.args[0] for call in network.call_args_list])
        self.assertEqual(7, network.call_count)

    def test_legacy_three_provider_sweep_remains_unchanged(self):
        with patch.object(mod, 'probe', side_effect=lambda source, origin: {
            'provider': source, 'state': 'results_observed'
        }) as network, patch('builtins.print'):
            self.assertEqual(0, mod.main(['--allow-provider-egress']))
        self.assertEqual(list(mod.LEGACY_SOURCES), [call.args[0] for call in network.call_args_list])
        self.assertEqual(3, network.call_count)

    def test_mixed_results_and_errors_are_reported_as_partial_not_success(self):
        def fake_transport(req, timeout):
            return BytesIO(json.dumps({
                'goreecloud': {'selected_engines': ['startpage'],
                               'represented_engines': ['startpage'],
                               'represented_result_counts': {'startpage': 1},
                               'representation_not_contact_confirmation': True},
                'results': [{'url': 'https://public.example.org',
                             'engine': 'startpage', 'engines': ['startpage']}],
                'unresponsive_engines': [['startpage', 'TimeoutException']],
            }).encode())
        output = mod.probe('startpage', 'http://127.0.0.1:8888',
                           transport=fake_transport)
        self.assertEqual('partial_results', output['state'])
        self.assertEqual(1, output['result_count'])
        self.assertEqual(1, output['error_count'])
        self.assertEqual(['timeout'], output['error_categories'])
        self.assertNotIn('TimeoutException', str(output))

    def test_error_categories_are_fixed_and_do_not_expose_upstream_messages(self):
        examples = (
            ('SearxEngineTooManyRequestsException', 'rate_limited'),
            ('HTTP error 403', 'access_denied'),
            ('HTTP error', 'upstream_http_error'),
            ('HTTP status unknown', 'upstream_http_error'),
            ('server API error', 'upstream_api_error'),
            ('unexpected crash', 'engine_error'),
            ('Cloudflare CAPTCHA', 'challenge'),
            ('parser failed secret=synthetic', 'parsing_error'),
            ('ConnectionError url=https://example.org/q=synthetic', 'network_error'),
            ('other secret=synthetic', 'other_error'),
        )
        for message, category in examples:
            with self.subTest(category=category):
                def fake_transport(req, timeout):
                    return BytesIO(json.dumps({
                        'goreecloud': {'selected_engines': ['bing']},
                        'results': [],
                        'unresponsive_engines': [['bing', message]],
                    }).encode())
                output = mod.probe('bing', 'http://127.0.0.1:8888',
                                   transport=fake_transport)
                self.assertEqual('provider_error', output['state'])
                self.assertEqual([category], output['error_categories'])
                self.assertNotIn('synthetic', str(output))
                self.assertNotIn(message, str(output))

    def test_malformed_or_other_source_error_attribution_is_rejected(self):
        invalid = (
            ['invalid'], [['google', 'TimeoutException']],
            [['brave']], [[None, 'timeout']], [['brave', None]],
            [{'engine': 'brave', 'error': 'timeout'}],
        )
        for errors in invalid:
            with self.subTest(errors=errors):
                def fake_transport(req, timeout):
                    return BytesIO(json.dumps({
                        'goreecloud': {'selected_engines': ['brave']},
                        'results': [],
                        'unresponsive_engines': errors,
                    }).encode())
                output = mod.probe('brave', 'http://127.0.0.1:8888',
                                   transport=fake_transport)
                self.assertEqual('invalid_error_contract', output['state'])
                self.assertNotIn('TimeoutException', str(output))

    def test_decode_error_omits_exception_details(self):
        def fails(req, timeout):
            raise OSError('synthetic sensitive URL')
        result = mod.probe('brave', 'http://localhost:8888', transport=fails)
        self.assertEqual('request_or_decode_error', result['state'])
        self.assertNotIn('synthetic sensitive URL', str(result))


    def test_category_adapter_registry_matches_dispatch_allowlist(self):
        from searx.goreecloud_policy import SEARCH_SOURCE_FAMILIES
        self.assertEqual(SEARCH_SOURCE_FAMILIES, mod.CATEGORY_ENGINES)

    def test_each_category_uses_exact_engine_and_category_flag(self):
        for category, mapping in mod.CATEGORY_ENGINES.items():
            for source, engine in mapping.items():
                with self.subTest(category=category, source=source):
                    captured = []
                    def respond(req, timeout):
                        captured.append(req)
                        return BytesIO(json.dumps({
                            'goreecloud': {'selected_engines': [engine],
                                           'represented_engines': [engine],
                                           'represented_result_counts': {engine: 1},
                                           'representation_not_contact_confirmation': True},
                            'results': [{'url': 'https://public.example.org',
                                         'engine': engine, 'engines': [engine]}],
                            'unresponsive_engines': [],
                        }).encode())
                    output = mod.probe(source, 'http://localhost:8888',
                                       category=category, transport=respond)
                    self.assertEqual('results_observed', output['state'])
                    self.assertEqual('POST', captured[0].get_method())
                    self.assertEqual('http://127.0.0.1:8888/search', captured[0].full_url)
                    fields = parse_qs(captured[0].data.decode())
                    self.assertEqual([engine], fields['engines'])
                    self.assertEqual(['json'], fields['format'])
                    category_flags = [key for key in fields if key.startswith('category_')]
                    self.assertEqual([] if category == 'general' else
                                     ['category_' + category], category_flags)

    def test_unsupported_provider_category_is_rejected_without_request(self):
        network = MagicMock()
        for source, category in (
            ('ecosia', 'images'), ('ecosia', 'news'), ('ecosia', 'videos'),
            ('startpage', 'videos'), ('brave', 'map'), ('unapproved', 'general'),
        ):
            with self.subTest(source=source, category=category):
                with self.assertRaises(ValueError):
                    mod.probe(source, 'http://localhost:8888',
                              category=category, transport=network)
        network.assert_not_called()

    def test_category_response_requires_exact_adapter_not_family(self):
        for error_case, expected in ((False, 'selection_mismatch'),
                                     (True, 'invalid_error_contract')):
            def respond(req, timeout):
                return BytesIO(json.dumps({
                    'goreecloud': {'selected_engines':
                                   ['qwant images'] if error_case else ['qwant']},
                    'results': [],
                    'unresponsive_engines': [['qwant', 'timeout']] if error_case else [],
                }).encode())
            outcome = mod.probe('qwant', 'http://localhost:8888',
                                category='images', transport=respond)
            self.assertEqual(expected, outcome['state'])


    def test_explicit_category_all_only_sweeps_supported_sources(self):
        with patch.object(mod, 'probe') as network, patch('builtins.print'):
            for category in mod.CATEGORY_ENGINES:
                self.assertEqual(64, mod.main(['--provider', 'all', '--category', category]))
            network.assert_not_called()
        for category, mapping in mod.CATEGORY_ENGINES.items():
            with self.subTest(category=category):
                with patch.object(mod, 'probe', side_effect=lambda source, origin, **opts: {
                    'provider': source, 'state': 'results_observed'
                }) as network, patch('builtins.print'):
                    self.assertEqual(0, mod.main([
                        '--provider', 'all', '--category', category, '--allow-provider-egress'
                    ]))
                self.assertEqual(list(mapping), [call.args[0] for call in network.call_args_list])
                for call in network.call_args_list:
                    self.assertEqual({} if category == 'general' else
                                     {'category': category}, call.kwargs)

    def test_category_is_disclosed_in_privacy_safe_summary(self):
        with patch.object(mod, 'probe', return_value={
            'provider': 'bing', 'state': 'results_observed'
        }), patch('builtins.print') as output:
            self.assertEqual(0, mod.main([
                '--provider', 'bing', '--category', 'news', '--allow-provider-egress'
            ]))
        result = json.loads(output.call_args.args[0])
        self.assertEqual('news', result['category'])
        self.assertTrue(result['development_only'])
        self.assertNotIn(mod.QUERY, str(result))

    def test_invalid_category_sweep_aborts_before_any_request(self):
        with patch.object(mod, 'probe') as network, patch('builtins.print'), patch('sys.stderr'):
            with self.assertRaises(SystemExit) as caught:
                mod.main(['--category', 'videos', '--allow-provider-egress'])
            self.assertEqual(2, caught.exception.code)
            network.assert_not_called()

if __name__ == '__main__':
    unittest.main()
