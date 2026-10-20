"""Real curl_cffi transport fails closed against a rejecting loopback SOCKS5H relay.

No Tor, public DNS lookup, or real search provider is involved. The fake SOCKS
relay records CONNECT hostnames but never opens an upstream connection.
"""
import asyncio
import os
from pathlib import Path
import socket
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-real-socks-failclosed-tests-only-0000')

from curl_cffi.requests.exceptions import ProxyError
from searx.network.network import Network


def read_exact(sock, count):
    data = b''
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise EOFError('Synthetic SOCKS handshake closed')
        data += chunk
    return data


class RejectingSocksGateway:
    """SOCKS5 mock that captures the remote-DNS target then denies it."""

    def __init__(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(3)
        self.listener.settimeout(6)
        self.port = self.listener.getsockname()[1]
        self.targets = []
        self.errors = []
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def serve(self):
        try:
            with self.listener.accept()[0] as peer:
                peer.settimeout(4)
                greeting = read_exact(peer, 2)
                if greeting[0] != 5:
                    raise ValueError('Not SOCKS5')
                methods = read_exact(peer, greeting[1])
                if 0 not in methods:
                    raise ValueError('SOCKS5 no-auth method missing')
                peer.sendall(bytes((5, 0)))
                request = read_exact(peer, 4)
                if request != bytes((5, 1, 0, 3)):
                    raise ValueError('Expected remote-DNS SOCKS5 CONNECT')
                hostname = read_exact(peer, read_exact(peer, 1)[0]).decode('ascii')
                port = int.from_bytes(read_exact(peer, 2), 'big')
                self.targets.append((hostname, port))
                # SOCKS5: connection refused, no upstream or DNS request.
                peer.sendall(bytes((5, 5, 0, 1)) + bytes(6))
        except (OSError, EOFError, ValueError) as error:
            self.errors.append(type(error).__name__)

    def __exit__(self, *_):
        self.listener.close()
        self.thread.join(timeout=7)
        if self.thread.is_alive():
            self.errors.append('GatewayThreadStillRunning')


class RealCurlSocksFailClosedTests(unittest.TestCase):
    @staticmethod
    def private_network(port):
        return Network(
            enable_http=False,
            verify=True,
            proxies={'all://': f'socks5h://127.0.0.1:{port}'},
            privacy_proxy_required=True,
            using_tor_proxy=True,
            retries=0,
        )

    def test_real_curl_refuses_provider_after_failed_tor_attestation(self):
        with RejectingSocksGateway() as gateway:
            network = self.private_network(gateway.port)
            with self.assertRaisesRegex(ProxyError, 'Tor verification failed'):
                asyncio.run(network.request(
                    'GET', 'https://search-provider.example.org/?q=synthetic-only',
                    raise_for_httperror=False,
                ))
        self.assertEqual([], gateway.errors)
        self.assertEqual([('check.torproject.org', 443)], gateway.targets)
        self.assertEqual({}, network._clients, 'Failed verification must revoke the client')

    def test_missing_socks_gateway_fails_closed_for_requests_and_streams(self):
        # Reserve a bound, non-listening loopback port throughout the test.
        # A reserved port eliminates races with unrelated local services.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserved:
            reserved.bind(('127.0.0.1', 0))
            network = self.private_network(reserved.getsockname()[1])

            async def verify_failure():
                for stream in (False, True):
                    with self.subTest(stream=stream):
                        call = network.stream if stream else network.request
                        with self.assertRaisesRegex(ProxyError, 'Tor verification failed'):
                            await call('GET', 'https://search-provider.example.org/')
                await network.aclose()

            asyncio.run(verify_failure())
        self.assertEqual({}, network._clients)


if __name__ == '__main__':
    unittest.main()
