"""Offline contracts for privacy-preserving non-Tor GoreeCloud Search egress.

A hosted Search instance masks the visitor's IP with the operator's server IP.
That is not anonymity; no tests here access real search providers.
"""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'synthetic-privacy-non-tor-verification-only-20261017')

from curl_cffi import CurlOpt
from curl_cffi.requests.exceptions import ProxyError
from searx import enforce_branded_private_transport
from searx.network.network import Network
from searx.network.client import new_client


class NonTorEgressTests(unittest.TestCase):
    def setUp(self):
        self.server_network = Network(
            enable_http=False, proxies={}, privacy_proxy_required=True,
            privacy_egress_mode='server_masked', server_masked_acknowledged=True,
        )

    def test_goreecloud_brand_cannot_disable_browser_private_transport(self):
        for profile in ({}, {'private_search': False}, {'private_search': None}):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                enforce_branded_private_transport({
                    'general': {'instance_name': 'GoreeCloud Search'},
                    'goreecloud': profile,
                })
        enforce_branded_private_transport({
            'general': {'instance_name': 'GoreeCloud Search'},
            'goreecloud': {'private_search': True},
        })
        enforce_branded_private_transport({
            'general': {'instance_name': 'Generic SearXNG'},
            'goreecloud': {},
        })

    def test_development_profiles_do_not_require_tor(self):
        import yaml
        gateway = yaml.safe_load((ROOT / 'configs/goreecloud/settings.yml').read_text(encoding='utf-8'))
        hosted = yaml.safe_load(
            (ROOT / 'configs/goreecloud/server-masked-staging.yml').read_text(encoding='utf-8'))
        self.assertEqual('gateway', gateway['goreecloud']['egress_mode'])
        self.assertEqual('server_masked', hosted['goreecloud']['egress_mode'])
        self.assertFalse(gateway['outgoing']['using_tor_proxy'])
        self.assertFalse(hosted['outgoing']['using_tor_proxy'])
        self.assertEqual({}, hosted['outgoing']['proxies'])
        self.assertTrue(hosted['goreecloud']['server_masked_acknowledged'])
        self.assertEqual('127.0.0.1', hosted['server']['bind_address'])
        self.assertFalse(hosted['server']['public_instance'])
        self.assertEqual(
            set(gateway['use_default_settings']['engines']['keep_only']),
            set(hosted['use_default_settings']['engines']['keep_only']),
        )

    def test_server_masking_is_blocked_without_separate_host_ack(self):
        with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '0'}):
            with patch('searx.network.network.new_client') as make:
                with self.assertRaises(ProxyError):
                    asyncio.run(self.server_network.get_client())
                make.assert_not_called()
        not_acknowledged = Network(
            enable_http=False, proxies={}, privacy_proxy_required=True,
            privacy_egress_mode='server_masked', server_masked_acknowledged=False,
        )
        with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '1'}):
            with patch('searx.network.network.new_client') as make:
                with self.assertRaises(ProxyError):
                    asyncio.run(not_acknowledged.get_client())
                make.assert_not_called()

    def test_server_masking_requires_no_unapproved_gateway(self):
        network = Network(
            enable_http=False,
            proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True,
            privacy_egress_mode='server_masked',
            server_masked_acknowledged=True,
        )
        with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '1'}):
            with patch('searx.network.network.new_client') as make:
                with self.assertRaises(ProxyError):
                    asyncio.run(network.get_client())
                make.assert_not_called()

    def test_hosted_mode_sends_via_backend_without_tor(self):
        client = Mock(is_closed=False)
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        client.get = AsyncMock(side_effect=AssertionError('Tor check must not run'))
        headers = {
            'X-Forwarded-For': '198.51.100.8',
            'X-Forwarded-Prefix': '/private',
            'X-B3-Traceid': 'client-trace',
            'Traceparent': 'client-trace',
            'Referer': 'https://somewhere.example/',
            'Origin': 'https://somewhere.example',
            'Sec-Ch-Ua': 'identifying',
            'Cookie': 'session=secret',
            'Accept': 'application/json',
        }
        with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '1'}):
            with patch('searx.network.network.new_client', return_value=client) as make:
                result = asyncio.run(self.server_network.request(
                    'GET', 'https://search.example.org/?q=public-synthetic',
                    headers=headers, cookies={'session': 'tracking'},
                    raise_for_httperror=False))
        self.assertEqual(200, result.status_code)
        self.assertEqual({}, make.call_args.args[5])
        self.assertIs(True, make.call_args.kwargs['disable_env_proxy'])
        self.assertEqual({'Accept': 'application/json'}, client.request.call_args.kwargs['headers'])
        self.assertNotIn('cookies', client.request.call_args.kwargs)
        client.get.assert_not_awaited()

    def test_server_masking_rejects_http_and_tls_or_protocol_bypass(self):
        with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '1'}):
            with patch('searx.network.network.new_client') as make:
                for url, kwargs in (
                    ('http://search.example.org/', {}),
                    ('https://search.example.org/', {'proxy': 'http://bad.example'}),
                    ('https://search.example.org/', {'verify': False}),
                    ('https://search.example.org/', {'enable_http3': True}),
                    ('https://search.example.org/', {'curl_options': {1: 'unsafe'}}),
                ):
                    with self.subTest(url=url, kwargs=kwargs):
                        with self.assertRaises(ProxyError):
                            asyncio.run(self.server_network.request('GET', url, **kwargs))
                make.assert_not_called()

    def test_approved_non_tor_gateway_never_calls_tor_check(self):
        gateway = Network(
            enable_http=False, proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True, privacy_egress_mode='gateway',
            using_tor_proxy=False,
        )
        client = Mock(is_closed=False)
        client.get = AsyncMock(side_effect=AssertionError('Tor check must not run'))
        with patch('searx.network.network.new_client', return_value=client) as make:
            self.assertIs(client, asyncio.run(gateway.get_client()))
        client.get.assert_not_awaited()
        self.assertEqual('socks5h://127.0.0.1:9050', make.call_args.args[5]['all://'])

    def test_unrecognized_mode_is_not_direct_fallback(self):
        network = Network(
            enable_http=False, proxies={}, privacy_proxy_required=True,
            privacy_egress_mode='unknown', server_masked_acknowledged=True,
        )
        with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '1'}):
            with patch('searx.network.network.new_client') as make:
                with self.assertRaises(ProxyError):
                    asyncio.run(network.get_client())
                make.assert_not_called()

    def test_server_client_explicitly_cancels_ambient_proxy(self):
        with patch('searx.network.client.AsyncClient') as factory:
            new_client(
                enable_http=False, verify=True, enable_http2=False,
                enable_http3=False, max_connections=3, proxies={},
                local_address=None, max_redirects=5,
                disable_env_proxy=True,
            )
        opts = factory.call_args.kwargs['curl_options']
        self.assertEqual('', opts[CurlOpt.PROXY])
        self.assertTrue(factory.call_args.kwargs['discard_cookies'])


if __name__ == '__main__':
    unittest.main()
