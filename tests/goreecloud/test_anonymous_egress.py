"""Anonymous egress contracts for GoreeCloud private Search.

No test requires Tor or sends external provider requests.
"""
import asyncio
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock, patch

# unittest discovers this file first. Establish the private profile before
# the first searx import so other app tests inherit the correct settings.
ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-private-egress-tests-only-000000000')

from curl_cffi.requests.exceptions import ProxyError

from searx.network.network import Network
from searx.network.client import _proxy_kwargs


class AnonymousEgressTests(unittest.TestCase):
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
            using_tor_proxy=True,
        )
        client = Mock()
        client.is_closed = False
        with patch('searx.network.network.new_client', return_value=client) as factory, \
             patch.object(Network, 'check_tor_proxy', new=AsyncMock(return_value=True)):
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
            with self.assertRaises(ProxyError):
                asyncio.run(n.get_client(verify=False))
            with self.assertRaises(ProxyError):
                asyncio.run(n.get_client(curl_options={1: 1}))
            factory.assert_not_called()

    def test_identifying_headers_and_cookies_do_not_leave(self):
        n = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
            using_tor_proxy=True,
        )
        from types import SimpleNamespace
        client = Mock(is_closed=False)
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        with patch('searx.network.network.new_client', return_value=client), \
             patch.object(Network, 'check_tor_proxy', new=AsyncMock(return_value=True)):
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

    def test_private_egress_rejects_disabled_tor_verification(self):
        """A valid local SOCKS endpoint is not proof of Tor anonymity."""
        n = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
            using_tor_proxy=False,
        )
        with patch('searx.network.network.new_client') as factory:
            with self.assertRaisesRegex(ProxyError, 'Tor attestation'):
                asyncio.run(n.get_client())
            factory.assert_not_called()

    def test_tor_attestation_rechecks_reused_client_and_revokes_on_failure(self):
        """Replaced local relays must not inherit a prior positive IsTor verdict."""
        good = Mock(status_code=200)
        good.json.return_value = {'IsTor': True}
        bad = Mock(status_code=200)
        bad.json.return_value = {'IsTor': False}
        first = Mock(is_closed=False)
        first.get = AsyncMock(side_effect=[good, bad])
        first.aclose = AsyncMock()
        second = Mock(is_closed=False)
        second.get = AsyncMock(return_value=good)
        second.aclose = AsyncMock()
        n = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
            using_tor_proxy=True,
        )
        with patch('searx.network.network.new_client',
                   side_effect=[first, second]) as factory:
            self.assertIs(asyncio.run(n.get_client()), first)
            with self.assertRaisesRegex(ProxyError, 'Tor verification failed'):
                asyncio.run(n.get_client())
            first.aclose.assert_awaited_once()
            self.assertFalse(n._clients, 'Revoked client must not be cached')
            self.assertIs(asyncio.run(n.get_client()), second)
            self.assertEqual(2, factory.call_count)
        self.assertEqual(2, first.get.await_count)
        for request in first.get.await_args_list + second.get.await_args_list:
            self.assertEqual(8, request.kwargs['timeout'])
            self.assertIs(request.kwargs['allow_redirects'], False)

    def test_tor_attestation_denies_bad_status_payload_and_transport_error(self):
        proxy = (('all://', 'socks5h://127.0.0.1:9050'),)
        invalid_responses = [
            (200, {'IsTor': False}),
            (200, {'IsTor': 'true'}),
            (200, {}),
            (200, []),
            (403, {'IsTor': True}),
        ]
        for status, payload in invalid_responses:
            with self.subTest(status=status, payload=payload):
                response = Mock(status_code=status)
                response.json.return_value = payload
                client = Mock()
                client.get = AsyncMock(return_value=response)
                self.assertFalse(asyncio.run(Network.check_tor_proxy(client, proxy)))
                client.get.assert_awaited_once()
        client = Mock()
        client.get = AsyncMock(side_effect=OSError('synthetic proxy failure'))
        self.assertFalse(asyncio.run(Network.check_tor_proxy(client, proxy)))
        client.get.assert_awaited_once()

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


if __name__ == '__main__':
    unittest.main()
