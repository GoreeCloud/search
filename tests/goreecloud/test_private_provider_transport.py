"""Fail-closed privacy regressions for provider transport (synthetic, offline)."""
import asyncio
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-private-transport-tests-only-0000000')

from curl_cffi.requests.exceptions import ProxyError
from searx.goreecloud_policy import safe_external_media_url
from searx.network.network import Network


def private_network(*, tor=False):
    return Network(
        enable_http=False, verify=True,
        proxies={'all://': 'socks5h://127.0.0.1:9050'},
        privacy_proxy_required=True, using_tor_proxy=tor,
    )


class PrivateProviderTransportTests(unittest.TestCase):
    def test_url_guard_rejects_local_metadata_ambiguous_and_malformed_hosts(self):
        self.assertTrue(safe_external_media_url('https://search.example.org/?q=synthetic'))
        self.assertTrue(safe_external_media_url('https://search.example.org:443/web'))
        self.assertFalse(safe_external_media_url(None))
        for url in (
            'http://search.example.org/', 'https://localhost/',
            'https://127.0.0.1/', 'https://169.254.169.254/latest/meta-data/',
            'https://[::1]/', 'https://127.1/', 'https://1.2.3.4.nip.io:8080/',
            'https://search.example.org:8443/', 'https://user:pass@search.example.org/',
            'https://host.internal/', 'https://search.example.org#frag',
            'https://search.example.org\\@169.254.169.254/',
            'https://search.example.org/%0a\nheader',
            'https://search.example.org:invalid/',
            'https://search.example.org./', 'https://search.invalid/',
            'https://metadata.google.internal/', 'https://host.local/',
        ):
            with self.subTest(url=url):
                self.assertFalse(safe_external_media_url(url))
                with patch('searx.network.network.new_client') as factory:
                    with self.assertRaises(ProxyError):
                        asyncio.run(private_network().request('GET', url))
                    factory.assert_not_called()

    def test_redirect_overrides_are_ignored_and_headers_sanitized(self):
        net = private_network()
        client = Mock(is_closed=False)
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        client.stream = Mock(return_value='synthetic-stream')
        with patch('searx.network.network.new_client', return_value=client):
            response = asyncio.run(net.request(
                'GET', 'https://search.example.org/path',
                headers={
                    'X-Forwarded-For': '192.0.2.50', 'Referer': 'https://private.example.org/',
                    'Origin': 'https://private.example.org', 'Sec-Fetch-Mode': 'navigate',
                    'X-B3-TraceId': 'synthetic', 'Accept': 'text/html',
                },
                cookies={'id': 'private'}, allow_redirects=True, raise_for_httperror=False,
            ))
            self.assertEqual(200, response.status_code)
            self.assertEqual('synthetic-stream', asyncio.run(
                net.stream('GET', 'https://search.example.org/path', allow_redirects=True)
            ))
        sent = client.request.call_args.kwargs
        self.assertIs(False, sent['allow_redirects'])
        self.assertEqual({'Accept': 'text/html'}, sent['headers'])
        self.assertNotIn('cookies', sent)
        self.assertIs(False, client.stream.call_args.kwargs['allow_redirects'])

    def test_tor_verification_rechecks_reused_clients_and_revokes_on_failure(self):
        net = private_network(tor=True)
        client = Mock(is_closed=False)
        client.get = AsyncMock(side_effect=[
            SimpleNamespace(status_code=200, json=lambda: {'IsTor': True}),
            SimpleNamespace(status_code=200, json=lambda: {'IsTor': True}),
            SimpleNamespace(status_code=200, json=lambda: {'IsTor': False}),
        ])
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        client.aclose = AsyncMock()

        async def checks():
            for _ in range(2):
                await net.request('GET', 'https://search.example.org/path',
                                  raise_for_httperror=False)
            with self.assertRaises(ProxyError):
                await net.request('GET', 'https://search.example.org/path',
                                  raise_for_httperror=False)

        with patch('searx.network.network.new_client', return_value=client) as factory:
            asyncio.run(checks())
            factory.assert_called_once()
        self.assertEqual(3, client.get.await_count)
        self.assertEqual(2, client.request.await_count)
        for call in client.get.await_args_list:
            self.assertEqual('https://check.torproject.org/api/ip', call.args[0])
            self.assertIs(False, call.kwargs['allow_redirects'])
            self.assertEqual(8, call.kwargs['timeout'])
        client.aclose.assert_awaited_once()
        self.assertFalse(net._clients)

    def test_malformed_tor_attestation_is_never_accepted(self):
        proxies = (('all://', 'socks5h://127.0.0.1:9050'),)
        for payload in ({'IsTor': 'true'}, {'IsTor': 1}, {}, [], None):
            with self.subTest(payload=payload):
                client = Mock()
                client.get = AsyncMock(return_value=SimpleNamespace(
                    status_code=200, json=lambda: payload))
                self.assertFalse(asyncio.run(Network.check_tor_proxy(client, proxies)))
        client = Mock()
        client.get = AsyncMock(side_effect=OSError('synthetic unavailable'))
        self.assertFalse(asyncio.run(Network.check_tor_proxy(client, proxies)))


if __name__ == '__main__':
    unittest.main()
