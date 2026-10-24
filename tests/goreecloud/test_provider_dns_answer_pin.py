"""Offline preconnection DNS answer pinning contract for guarded provider egress."""

import asyncio
import os
from pathlib import Path
import socket
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.free-first.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-dns-answer-pin-tests-only-0000000')

from curl_cffi import CurlOpt
from curl_cffi.requests.exceptions import ProxyError

from searx.network.network import Network
from searx.network.client import new_client


def guarded(**kwargs):
    return Network(enable_http=False, verify=True, provider_target_guard_required=True, **kwargs)


def dns_answers(*addresses):
    return [(socket.AF_INET6 if ':' in addr else socket.AF_INET,
             socket.SOCK_STREAM, 6, '', (addr, 443)) for addr in addresses]


class ProviderDnsAnswerPinTests(unittest.TestCase):
    def test_installed_libcurl_resolve_option_reaches_only_loopback_fixture(self):
        # Exercise actual libcurl on a disposable loopback port. The hostname
        # is deliberately nonresolvable; without CURLOPT_RESOLVE this cannot
        # connect to the fixture. No external provider traffic is initiated.
        accepted = threading.Event()
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except PermissionError:
            self.skipTest('Socket creation disabled by the execution sandbox')
        with server_socket as server:
            server.bind(('127.0.0.1', 0))
            server.listen(1)
            server.settimeout(4)
            port = server.getsockname()[1]

            def serve_once():
                try:
                    connection, _ = server.accept()
                    with connection:
                        accepted.set()
                except OSError:
                    pass

            worker = threading.Thread(target=serve_once, daemon=True)
            worker.start()

            async def try_pinned_connection():
                client = new_client(
                    False, True, False, False, 1, {}, None, 0,
                    curl_options={
                        CurlOpt.RESOLVE: [f'unresolvable.invalid:{port}:127.0.0.1'],
                        CurlOpt.PROXY: '',
                    },
                )
                try:
                    with self.assertRaises(Exception):
                        # Loopback fixture closes without TLS, by design.
                        await client.get(f'https://unresolvable.invalid:{port}/', timeout=2)
                finally:
                    await client.aclose()

            with patch.dict(os.environ, {
                'HTTPS_PROXY': 'http://127.0.0.1:9',
                'ALL_PROXY': 'http://127.0.0.1:9',
            }):
                asyncio.run(try_pinned_connection())
            worker.join(timeout=1)
            self.assertTrue(accepted.is_set(), 'Installed libcurl did not honor pinned address')

    def test_all_public_answers_pin_curl_without_resolving_again(self):
        network = guarded()
        client = Mock(is_closed=False)
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        loop_getaddrinfo = AsyncMock(return_value=dns_answers('8.8.8.8', '1.1.1.1', '8.8.8.8'))

        async def request():
            loop = asyncio.get_running_loop()
            with patch.object(loop, 'getaddrinfo', new=loop_getaddrinfo):
                return await network.request('GET', 'https://source.example.org/search', raise_for_httperror=False)

        with patch('searx.network.network.new_client', return_value=client) as factory:
            response = asyncio.run(request())

        self.assertEqual(200, response.status_code)
        loop_getaddrinfo.assert_awaited_once_with('source.example.org', 443, type=socket.SOCK_STREAM)
        options = factory.call_args.kwargs['curl_options']
        self.assertEqual({
            CurlOpt.RESOLVE: ['source.example.org:443:1.1.1.1,8.8.8.8'],
            CurlOpt.PROXY: '',
        }, options)
        self.assertIs(True, factory.call_args.args[1])  # TLS certificate verification retained.
        self.assertIs(False, factory.call_args.args[3])  # QUIC remains disabled.

    def test_ipv6_public_answers_use_curl_bracket_grammar(self):
        network = guarded()
        client = Mock(is_closed=False)
        client.request = AsyncMock(return_value=SimpleNamespace(status_code=200))
        with patch.object(Network, 'resolve_public_provider', new=AsyncMock(
            return_value=('source.example.org', ('2606:4700:4700::1111',))
        )), patch('searx.network.network.new_client', return_value=client) as factory:
            response = asyncio.run(network.request(
                'GET', 'https://source.example.org/', raise_for_httperror=False,
            ))
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            ['source.example.org:443:[2606:4700:4700::1111]'],
            factory.call_args.kwargs['curl_options'][CurlOpt.RESOLVE],
        )

    def test_non_global_and_mixed_dns_answer_sets_fail_before_client(self):
        for addresses in (
            ('127.0.0.1',), ('169.254.169.254',), ('10.10.0.5',),
            ('::1',), ('fc00::1',), ('8.8.8.8', '192.168.1.3'),
            ('2606:4700:4700::1111', 'fe80::1'), ('192.0.2.10',),
            # is_global=True is insufficient for addresses carrying
            # privately routed IPv4 through an IPv6 translation network.
            ('64:ff9b::a9fe:a9fe',), ('64:ff9b:1::a9fe:a9fe',),
            ('::ffff:8.8.8.8',),
            (),
        ):
            with self.subTest(addresses=addresses):
                net = guarded()

                async def request():
                    with patch.object(asyncio.get_running_loop(), 'getaddrinfo',
                                      new=AsyncMock(return_value=dns_answers(*addresses))):
                        return await net.request('GET', 'https://source.example.org/')

                with patch('searx.network.network.new_client') as factory:
                    with self.assertRaises(ProxyError):
                        asyncio.run(request())
                    factory.assert_not_called()

    def test_resolver_failures_and_excessive_answers_fail_closed(self):
        for result in (
            socket.gaierror('resolver down'), asyncio.TimeoutError(),
            dns_answers(*(f'8.8.8.{n}' for n in range(1, 19))),
        ):
            with self.subTest(result=str(result)[:60]):
                async def request():
                    resolver = AsyncMock(side_effect=result) if isinstance(result, Exception) else AsyncMock(return_value=result)
                    with patch.object(asyncio.get_running_loop(), 'getaddrinfo', new=resolver):
                        return await guarded().request('GET', 'https://source.example.org/')

                with patch('searx.network.network.new_client') as factory:
                    with self.assertRaises(ProxyError):
                        asyncio.run(request())
                    factory.assert_not_called()

    def test_missing_pin_or_proxy_is_never_a_direct_connection_fallback(self):
        for net, pin in (
            (guarded(), None),
            (guarded(proxies={'all://': 'http://127.0.0.1:8080'}), ('source.example.org', ('8.8.8.8',))),
        ):
            with patch('searx.network.network.new_client') as factory:
                with self.assertRaises(ProxyError):
                    asyncio.run(net.get_client(_trusted_dns_pin=pin))
                factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
