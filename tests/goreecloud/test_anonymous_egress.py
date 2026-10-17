"""Privacy-by-default: never dispatch private Search through direct egress."""
import asyncio
import unittest
from unittest.mock import patch

from searx.goreecloud_anonymity import AnonymousEgressError, require_tor_route
from searx.network.client import new_client
from searx.network.network import Network
from curl_cffi.requests.exceptions import ProxyError

import test_runtime_smoke as smoke


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
