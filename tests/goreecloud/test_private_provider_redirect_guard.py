"""No private Search provider may redirect egress into other destinations.

Synthetic offline tests: no Tor and no live provider traffic.
"""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'synthetic-private-redirect-regression-20261017')

from curl_cffi.requests.exceptions import ProxyError
from searx.network.network import Network


class PrivateProviderRedirectGuardTests(unittest.TestCase):
    def setUp(self):
        self.network = Network(
            enable_http=False, proxies={}, privacy_proxy_required=True,
            privacy_egress_mode='server_masked', server_masked_acknowledged=True,
        )

    def test_initial_destination_fail_closed_before_opening_client(self):
        rejected = (
            'http://search.example.org/',
            'https://127.0.0.1/',
            'https://169.254.169.254/latest/meta-data/',
            'https://10.20.30.40/',
            'https://[::1]/',
            'https://localhost/',
            'https://metadata.internal/',
            'https://search.example.org:8080/',
            'https://secret@search.example.org/',
            'https://search.example.org\\@localhost/',
            'https://127.1/',
            'https://2130706433/',
            'https://search.example.org/#fragment',
            'https://search.example.org/\nheader:forged',
            'https://search.example.org/' + 'x' * 4200,
        )
        with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '1'}):
            with patch('searx.network.network.new_client') as make:
                for url in rejected:
                    with self.subTest(url=url[:90]), self.assertRaises(ProxyError):
                        asyncio.run(self.network.request('GET', url, raise_for_httperror=False))
                make.assert_not_called()

    def test_provider_redirects_are_not_followed_even_when_requested(self):
        client = Mock(is_closed=False)
        client.request = AsyncMock(return_value=SimpleNamespace(
            status_code=302, headers={'Location': 'https://127.0.0.1/internal'},
        ))
        with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '1'}):
            with patch('searx.network.network.new_client', return_value=client):
                for requested in (True, False):
                    with self.subTest(requested=requested):
                        response = asyncio.run(self.network.request(
                            'GET', 'https://search.example.org/synthetic',
                            allow_redirects=requested, raise_for_httperror=False,
                        ))
                        self.assertEqual(302, response.status_code)
                        self.assertIs(False, client.request.await_args.kwargs['allow_redirects'])
        self.assertEqual(2, client.request.await_count)

    def test_gateway_mode_refuses_private_targets_without_proxy_bypass(self):
        gateway = Network(
            enable_http=False, proxies={'all://': 'socks5h://127.0.0.1:9050'},
            privacy_proxy_required=True, privacy_egress_mode='gateway',
            using_tor_proxy=False,
        )
        with patch('searx.network.network.new_client') as make:
            for url in (
                'https://127.0.0.1/', 'https://169.254.169.254/',
                'https://internal.local/', 'https://example.org:8080/',
            ):
                with self.subTest(url=url), self.assertRaises(ProxyError):
                    asyncio.run(gateway.request('GET', url))
            make.assert_not_called()

    def test_streamed_media_and_request_paths_share_redirect_policy(self):
        client = Mock(is_closed=False)
        marker = object()
        client.stream = Mock(return_value=marker)
        with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '1'}):
            with patch('searx.network.network.new_client', return_value=client):
                response = asyncio.run(self.network.stream(
                    'GET', 'https://cdn.example.org/img.png',
                    allow_redirects=True,
                ))
                self.assertIs(marker, response)
                self.assertIs(False, client.stream.call_args.kwargs['allow_redirects'])

    def test_nonprivate_upstream_not_changed(self):
        plain = Network(enable_http=False, proxies={}, privacy_proxy_required=False)
        client = Mock(is_closed=False)
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        with patch('searx.network.network.new_client', return_value=client):
            result = asyncio.run(plain.request(
                'GET', 'https://search.example.org/', allow_redirects=True,
                raise_for_httperror=False,
            ))
        self.assertEqual(200, result.status_code)
        self.assertIs(True, client.request.call_args.kwargs['allow_redirects'])


if __name__ == '__main__':
    unittest.main()
