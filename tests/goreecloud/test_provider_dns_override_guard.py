"""Offline DNS/transport override regressions for guarded Search providers."""

import asyncio
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-dns-override-tests-only-0000000000')

from curl_cffi import CurlHttpVersion
from curl_cffi.requests.exceptions import ProxyError
from searx.network.network import Network


def guarded_network(*, tor=False):
    return Network(
        enable_http=False, verify=True,
        proxies={'all://': 'socks5h://127.0.0.1:9050'} if tor else {},
        using_tor_proxy=tor, privacy_proxy_required=tor,
        provider_target_guard_required=True,
    )


class ProviderDnsOverrideGuardTests(unittest.TestCase):
    def test_dns_resolver_override_fails_before_client_in_both_profiles(self):
        for tor in (False, True):
            for doh_url in ('https://127.0.0.1/dns-query', 'https://resolver.example.org/dns-query', None):
                with self.subTest(tor=tor, doh_url=doh_url):
                    with patch('searx.network.network.new_client') as factory:
                        with self.assertRaisesRegex(ProxyError, 'transport override'):
                            asyncio.run(guarded_network(tor=tor).request(
                                'GET', 'https://search.example.org/', doh_url=doh_url,
                            ))
                        factory.assert_not_called()

    def test_proxy_credentials_and_protocol_overrides_are_not_per_request(self):
        for kwargs in ({'proxy_auth': ('user', 'password')},
                       {'http_version': CurlHttpVersion.V3}):
            with self.subTest(kwargs=kwargs):
                with patch('searx.network.network.new_client') as factory:
                    with self.assertRaisesRegex(ProxyError, 'transport override'):
                        asyncio.run(guarded_network().request(
                            'GET', 'https://search.example.org/', **kwargs,
                        ))
                    factory.assert_not_called()

    def test_streaming_provider_requests_cannot_replace_dns_resolver(self):
        with patch('searx.network.network.new_client') as factory:
            with self.assertRaisesRegex(ProxyError, 'transport override'):
                asyncio.run(guarded_network().stream(
                    'GET', 'https://search.example.org/image',
                    doh_url='https://127.0.0.1/dns-query',
                ))
            factory.assert_not_called()

    def test_normal_free_first_https_request_remains_compatible(self):
        client = Mock(is_closed=False)
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        with patch('searx.network.network.new_client', return_value=client), patch.object(
            Network, 'resolve_public_provider', new=AsyncMock(return_value=('search.example.org', ('8.8.8.8',)))
        ):
            response = asyncio.run(guarded_network().request(
                'GET', 'https://search.example.org/',
                allow_redirects=True, raise_for_httperror=False,
            ))
        self.assertEqual(200, response.status_code)
        self.assertIs(False, client.request.call_args.kwargs['allow_redirects'])


if __name__ == '__main__':
    unittest.main()
