"""Anonymous egress contracts for GoreeCloud private Search.

No test requires Tor or sends external provider requests.
"""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

# unittest discovers this file first. Establish the private profile before
# the first searx import so other app tests inherit the correct settings.
ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-private-egress-tests-only-000000000')

from curl_cffi.requests.exceptions import ProxyError

from searx.network.network import Network, requires_private_egress
from searx.network.client import _proxy_kwargs


class AnonymousEgressTests(unittest.TestCase):
    def test_private_mode_always_requires_anonymous_egress(self):
        self.assertTrue(requires_private_egress({'goreecloud': {'private_search': True}}))
        self.assertTrue(requires_private_egress({'goreecloud': {
            'private_search': True, 'require_anonymous_egress': False,
        }}))
        self.assertTrue(requires_private_egress({'goreecloud': {
            'private_search': False, 'require_anonymous_egress': True,
        }}))
        self.assertTrue(requires_private_egress({'goreecloud': {
            'private_search': False, 'require_anonymous_egress': False,
        }}))
        self.assertTrue(requires_private_egress({'goreecloud': None}))
        self.assertTrue(requires_private_egress({'general': {
            'instance_name': 'GoreeCloud Search',
        }}))
        self.assertFalse(requires_private_egress({'general': {
            'instance_name': 'Generic SearXNG',
        }}))

    def test_only_local_socks5h_all_proxy_is_accepted(self):
        valid = (
            (('all://', 'socks5h://127.0.0.1:9050'),),
            (('all://', 'socks5h://[::1]:9050'),),
        )
        for config in valid:
            with self.subTest(config=config):
                self.assertTrue(Network.valid_private_proxy(config))
                self.assertEqual(
                    {'proxy': config[0][1]},
                    _proxy_kwargs(dict(config), enable_http=False),
                )
        invalid = [
            (), (('https://', 'socks5h://127.0.0.1:9050'),),
            (('all://', 'socks5://127.0.0.1:9050'),),
            (('all://', 'http://127.0.0.1:9050'),),
            (('all://', 'socks5h://tor.example:9050'),),
            (('all://', 'socks5h://127.0.0.2:9050'),),
            (('all://', 'socks5h://127.0.0.1'),),
            (('all://', 'socks5h://127.0.0.1:notaport'),),
            (('all://', 'socks5h://127.0.0.1:9050/?q=leak'),),
            (('all://', 'socks5h://name:pass@127.0.0.1:9050'),),
            (('all://', 'socks5h://127.0.0.1:9050 '),),
            (('all://', 'socks5h://127.0.0.1:9050'),
             ('https://', 'https://other.example:8080')),
        ]
        for config in invalid:
            with self.subTest(config=config):
                self.assertFalse(Network.valid_private_proxy(config))

    def test_unconfigured_private_egress_never_creates_direct_client(self):
        for proxy in (None, {}, 'http://127.0.0.1:8080',
                      {'all://': 'socks5h://another.example:9050'}):
            with self.subTest(proxy=proxy):
                n = Network(proxies=proxy, privacy_proxy_required=True)
                with patch('searx.network.network.new_client') as factory:
                    with self.assertRaises(ProxyError):
                        asyncio.run(n.request('GET', 'https://search.example.org/?q=private'))
                    factory.assert_not_called()

    def test_approved_gateway_is_passed_to_client(self):
        n = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
        )
        client = Mock()
        client.is_closed = False
        client.get = AsyncMock(return_value=SimpleNamespace(
            status_code=200, json=lambda: {'IsTor': True}))
        with patch('searx.network.network.new_client', return_value=client) as factory:
            self.assertIs(asyncio.run(n.get_client()), client)
            args = factory.call_args.args
            self.assertEqual({'all://': 'socks5h://127.0.0.1:9050'}, args[5])
            self.assertFalse(args[0], 'Plaintext HTTP must remain off')
            self.assertTrue(args[1], 'TLS validation must remain on')

    def test_request_overrides_and_plaintext_are_denied(self):
        n = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
        )
        cases = [
            ('http://search.example.org/', {}),
            ('https://search.example.org/', {'proxy': 'http://direct.example:80'}),
            ('https://search.example.org/', {'proxies': {'https': 'http://direct.example:80'}}),
            ('https://search.example.org/', {'interface': '0.0.0.0'}),
            ('https://search.example.org/', {'curl_options': {1: 'unsafe'}}),
        ]
        with patch('searx.network.network.new_client') as factory:
            for url, kwargs in cases:
                with self.subTest(url=url, kwargs=kwargs):
                    with self.assertRaises(ProxyError):
                        asyncio.run(n.request('GET', url, **kwargs))
            factory.assert_not_called()

    def test_disabled_tls_and_client_options_cannot_bypass_guard(self):
        n = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
        )
        with patch('searx.network.network.new_client') as factory:
            for untrusted in (False, 0, '/tmp/untrusted-test-ca.pem'):
                with self.subTest(verify=untrusted), self.assertRaises(ProxyError):
                    asyncio.run(n.get_client(verify=untrusted))
            with self.assertRaises(ProxyError):
                asyncio.run(n.get_client(curl_options={1: 1}))
            factory.assert_not_called()

    def test_identifying_headers_and_cookies_do_not_leave(self):
        n = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
        )
        client = Mock(is_closed=False)
        client.get = AsyncMock(return_value=SimpleNamespace(
            status_code=200, json=lambda: {'IsTor': True}))
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        with patch('searx.network.network.new_client', return_value=client):
            asyncio.run(n.request(
                'GET', 'https://search.example.org/?q=public',
                headers={
                    'Cookie': 'persistent=user123',
                    'X-Forwarded-For': '192.0.2.44',
                    'x-real-ip': '192.0.2.45',
                    'Authorization': 'Bearer secret',
                    'Accept': 'application/json',
                },
                cookies={'tracking': 'user123'},
                raise_for_httperror=False,
            ))
        forwarded = client.request.call_args.kwargs
        self.assertNotIn('cookies', forwarded)
        self.assertEqual(
            {'Accept': 'application/json'}, forwarded['headers']
        )
        self.assertEqual('https://search.example.org/?q=public',
                         client.request.call_args.args[1])

    def test_tor_attestation_rejects_untrusted_or_malformed_verdicts(self):
        proxy = (('all://', 'socks5h://127.0.0.1:9050'),)
        samples = [
            ({'IsTor': True}, 200, True),
            ({'IsTor': False}, 200, False),
            ({'IsTor': 'true'}, 200, False),
            ({'IsTor': 'false'}, 200, False),
            ({'IsTor': 1}, 200, False),
            ({}, 200, False),
            ([], 200, False),
            ({'IsTor': True}, 403, False),
        ]
        for data, status, expected in samples:
            with self.subTest(data=data, status=status):
                client = Mock()
                client.get = AsyncMock(return_value=SimpleNamespace(
                    status_code=status, json=lambda: data))
                self.assertIs(
                    asyncio.run(Network.check_tor_proxy(client, proxy)), expected)
                self.assertEqual(
                    'https://check.torproject.org/api/ip',
                    client.get.await_args.args[0])
                self.assertEqual(8, client.get.await_args.kwargs['timeout'])
                self.assertIs(False, client.get.await_args.kwargs['allow_redirects'])
        failed = Mock()
        failed.get = AsyncMock(side_effect=OSError('no proxy'))
        self.assertFalse(asyncio.run(Network.check_tor_proxy(failed, proxy)))

    def test_failed_tor_attestation_closes_client_before_any_search(self):
        network = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
            using_tor_proxy=True,  # Tor is explicitly optional, not a default.
        )
        client = Mock(is_closed=False)
        client.get = AsyncMock(return_value=SimpleNamespace(
            status_code=200, json=lambda: {'IsTor': False}))
        client.aclose = AsyncMock()
        client.request = AsyncMock()
        with patch('searx.network.network.new_client', return_value=client):
            with self.assertRaises(ProxyError):
                asyncio.run(network.request('GET', 'https://search.example.org/?q=private'))
        client.request.assert_not_awaited()
        client.aclose.assert_awaited_once()
        self.assertFalse(network._clients)

    def test_reused_session_requires_new_tor_attestation_every_request(self):
        network = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
            using_tor_proxy=True,  # Tor is explicitly optional, not a default.
        )
        client = Mock(is_closed=False)
        client.get = AsyncMock(return_value=SimpleNamespace(
            status_code=200, json=lambda: {'IsTor': True}))
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        with patch('searx.network.network.new_client', return_value=client) as factory:
            for _ in range(2):
                asyncio.run(network.request(
                    'GET', 'https://search.example.org/?q=public',
                    raise_for_httperror=False))
        factory.assert_called_once()
        self.assertEqual(2, client.get.await_count)
        self.assertEqual(2, client.request.await_count)

    def test_tor_attestation_revocation_blocks_reused_session(self):
        network = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
            using_tor_proxy=True,  # Tor is explicitly optional, not a default.
        )
        verdicts = [
            SimpleNamespace(status_code=200, json=lambda: {'IsTor': True}),
            SimpleNamespace(status_code=200, json=lambda: {'IsTor': False}),
        ]
        client = Mock(is_closed=False)
        client.get = AsyncMock(side_effect=verdicts)
        client.aclose = AsyncMock()
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        with patch('searx.network.network.new_client', return_value=client) as factory:
            asyncio.run(network.request(
                'GET', 'https://search.example.org/?q=public',
                raise_for_httperror=False))
            with self.assertRaises(ProxyError):
                asyncio.run(network.request(
                    'GET', 'https://search.example.org/?q=public',
                    raise_for_httperror=False))
        factory.assert_called_once()
        self.assertEqual(2, client.get.await_count)
        self.assertEqual(1, client.request.await_count)
        client.aclose.assert_awaited_once()
        self.assertFalse(network._clients)

    def test_private_profile_has_strict_egress_policy(self):
        import test_runtime_smoke as smoke
        from searx.network.network import NETWORKS
        self.assertTrue(smoke.settings['goreecloud']['require_anonymous_egress'])
        self.assertEqual(
            'socks5h://127.0.0.1:9050',
            smoke.settings['outgoing']['proxies']['all://'],
        )
        self.assertTrue(NETWORKS)
        self.assertTrue(all(n.privacy_proxy_required for n in NETWORKS.values()))
        self.assertTrue(all(n.privacy_egress_mode == 'gateway' for n in NETWORKS.values()))
        self.assertTrue(all(not n.using_tor_proxy for n in NETWORKS.values()))


if __name__ == '__main__':
    unittest.main()
