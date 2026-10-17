"""Privacy-by-default: never dispatch private Search through direct egress."""
import asyncio
import unittest
from unittest.mock import patch

import test_runtime_smoke as smoke

from searx.goreecloud_anonymity import AnonymousEgressError, require_tor_route
from searx.network.client import new_client
from searx.network.network import Network
from curl_cffi.requests.exceptions import ProxyError



class AnonymousSearchEgressTests(unittest.TestCase):
    def test_private_profile_requires_tor_for_all_outbound_networks(self):
        self.assertTrue(smoke.settings['goreecloud']['private_search'])
        self.assertTrue(smoke.settings['goreecloud']['require_anonymous_egress'])
        outgoing = smoke.settings['outgoing']
        self.assertTrue(outgoing['using_tor_proxy'])
        self.assertEqual(
            'socks5h://127.0.0.1:9050',
            require_tor_route(outgoing['proxies'], using_tor_proxy=outgoing['using_tor_proxy'])
        )

    def test_privacy_page_discloses_relay_failure_and_provider_visibility(self):
        with smoke.app.test_client() as client:
            response = client.get('/static/themes/simple/goreecloud/privacy.html')
            self.assertEqual(200, response.status_code)
            self.assertIn(b'verified Tor SOCKS5h', response.data)
            self.assertIn(b'provider still receives the query', response.data)
            self.assertIn(b'never falls back', response.data)
            response.close()

    def test_non_anonymous_routes_fail_closed(self):
        invalid = (
            ({}, True),
            ({'https://': 'socks5h://127.0.0.1:9050'}, True),
            ({'all://': 'http://127.0.0.1:9050'}, True),
            ({'all://': 'socks5://127.0.0.1:9050'}, True),
            ({'all://': 'socks5h://proxy.example:9050'}, True),
            ({'all://': 'socks5h://127.0.0.1:9050',
              'https://': 'https://proxy.example:443'}, True),
            ({'all://': 'socks5h://user:password@127.0.0.1:9050'}, True),
            ({'all://': 'socks5h://127.0.0.1:9050?q=secret'}, True),
            ({'all://': 'socks5h://127.0.0.1:9050'}, False),
            ({'all://': 'socks5h://127.0.0.1'}, True),
        )
        for proxies, verifies_tor in invalid:
            with self.subTest(route=str(proxies), verifies_tor=verifies_tor):
                with self.assertRaises(AnonymousEgressError) as caught:
                    require_tor_route(proxies, using_tor_proxy=verifies_tor)
                self.assertNotIn('password', str(caught.exception))
                self.assertNotIn('secret', str(caught.exception))

    def test_local_remote_dns_socks_route_is_allowed(self):
        self.assertEqual(
            'socks5h://[::1]:9150',
            require_tor_route({'all://': 'socks5h://[::1]:9150'}, using_tor_proxy=True)
        )

    def test_direct_client_creation_is_denied_before_transport(self):
        with patch('searx.network.client.AsyncClient') as construct:
            with self.assertRaises(AnonymousEgressError):
                new_client(
                    enable_http=False, verify=True, enable_http2=False,
                    enable_http3=False, max_connections=2, proxies={},
                    local_address=None, max_redirects=3,
                )
            construct.assert_not_called()

    def test_non_tor_proxy_never_reaches_search_provider(self):
        from types import SimpleNamespace

        class UntrustedRelay:
            is_closed = False

            def __init__(self):
                self.urls = []

            async def get(self, url, timeout):
                self.urls.append(url)
                return SimpleNamespace(json=lambda: {'IsTor': False})

            async def aclose(self):
                self.is_closed = True

        fake = UntrustedRelay()
        network = Network(
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            using_tor_proxy=True,
        )
        with patch.dict(Network._TOR_CHECK_RESULT, {}, clear=True), patch(
            'searx.network.network.new_client', return_value=fake
        ):
            with self.assertRaises(ProxyError):
                asyncio.run(network.get_client())
        self.assertEqual(['https://check.torproject.org/api/ip'], fake.urls)
        self.assertTrue(fake.is_closed)

    def test_private_profile_cannot_opt_out_of_anonymous_egress(self):
        for setting in (False, None):
            with self.subTest(setting=setting), patch.dict(
                smoke.settings['goreecloud'], {'require_anonymous_egress': setting}
            ), patch('searx.network.client.AsyncClient') as construct:
                with self.assertRaises(AnonymousEgressError):
                    new_client(
                        enable_http=False, verify=True, enable_http2=False,
                        enable_http3=False, max_connections=1,
                        proxies={'all://': 'socks5h://127.0.0.1:9050'},
                        local_address=None, max_redirects=2,
                    )
                construct.assert_not_called()

    def test_named_network_cannot_disable_tor_verification(self):
        network = Network(
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            using_tor_proxy=False,
        )
        with patch('searx.network.network.new_client') as construct:
            with self.assertRaises(ProxyError):
                asyncio.run(network.get_client())
            construct.assert_not_called()


if __name__ == '__main__':
    unittest.main()
