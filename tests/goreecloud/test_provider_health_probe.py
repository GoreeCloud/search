"""Offline contracts for the opt-in, loopback-only provider health probe."""
import importlib.util
import json
from io import BytesIO
from pathlib import Path
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
                'goreecloud': {'selected_engines': ['brave']},
                'results': [{'url': 'https://example.org'}],
                'unresponsive_engines': [],
            }).encode())
        result = mod.probe('brave', 'http://localhost:8888', transport=fake_transport)
        self.assertEqual('results_observed', result['state'])
        self.assertEqual('POST', seen[0].get_method())
        self.assertIn(b'engines=brave', seen[0].data)
        self.assertNotIn('verification', str(result))

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

    def test_decode_error_omits_exception_details(self):
        def fails(req, timeout):
            raise OSError('synthetic sensitive URL')
        result = mod.probe('brave', 'http://localhost:8888', transport=fails)
        self.assertEqual('request_or_decode_error', result['state'])
        self.assertNotIn('synthetic sensitive URL', str(result))


if __name__ == '__main__':
    unittest.main()
