"""Synthetic non-Tor SOCKS gateway tests: DNS safety without external traffic."""
import asyncio
import socket
import struct
import unittest
from unittest.mock import AsyncMock, Mock, patch

from utils import goreecloud_private_socks_gateway as gateway


def records(*addresses):
    results = []
    for address in addresses:
        family = socket.AF_INET6 if ':' in address else socket.AF_INET
        sockaddr = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
        results.append((family, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', sockaddr))
    return results


class GatewayDnsSafetyTests(unittest.TestCase):
    def test_staging_profile_is_remote_loopback_and_tor_free(self):
        from pathlib import Path
        import yaml
        path = Path(__file__).resolve().parents[2] / 'configs/goreecloud/dns-pinned-gateway-staging.yml'
        cfg = yaml.safe_load(path.read_text(encoding='utf-8'))
        self.assertEqual('gateway', cfg['goreecloud']['egress_mode'])
        self.assertIs(cfg['goreecloud']['private_search'], True)
        self.assertIs(cfg['goreecloud']['server_masked_acknowledged'], False)
        self.assertIs(cfg['outgoing']['using_tor_proxy'], False)
        self.assertEqual({'all://': 'socks5h://127.0.0.1:19050'},
                         cfg['outgoing']['proxies'])
        self.assertIs(cfg['server']['public_instance'], False)
        self.assertIs(cfg['server']['limiter'], False)
        self.assertEqual('127.0.0.1', cfg['server']['bind_address'])
        self.assertEqual('POST', cfg['server']['method'])

    def test_only_public_https_hostnames(self):
        allowed = ('search.example.org', 'cdn.example.com', 'xn--bcher-kva.example.org')
        for host in allowed:
            with self.subTest(host=host):
                self.assertTrue(gateway.external_hostname(host))
        denied = (
            'localhost', 'metadata.internal', 'search.local', 'a.home.arpa',
            '127.0.0.1', '169.254.169.254', '[::1]',
            '127.1', '0x7f000001', 'a.example.org:444',
            'a.example.org/path', 'a.example.org?x=1',
            'a.example.org#f', 'x@a.example.org', 'a.example.org\\@localhost',
            'a.example.org%2f', 'a.example.org\nX-Forwarded-For:hi',
            '', 'a.example.org ', None,
        )
        for host in denied:
            with self.subTest(host=str(host)):
                self.assertFalse(gateway.external_hostname(host))

    def test_pinned_address_accepts_public_dns_without_second_lookup(self):
        async def resolve(host, port, **kw):
            self.assertEqual(('search.example.org', 443), (host, port))
            return records('93.184.216.34', '2606:4700:4700::1111')

        family, address = asyncio.run(gateway.pinned_public_address(
            'search.example.org', 443, resolve=resolve,
        ))
        self.assertEqual((socket.AF_INET, '93.184.216.34'), (family, address))

    def test_refuse_any_nonpublic_answer_including_mixed_rebinding(self):
        blocks = (
            '127.0.0.1', '10.0.0.7', '192.168.1.1', '172.16.0.1',
            '169.254.169.254', '100.64.0.1', '0.0.0.0',
            '::1', 'fc00::1', 'fe80::1', '::ffff:127.0.0.1',
            '192.0.2.4', '198.51.100.12', '203.0.113.42',
        )
        for ip in blocks:
            async def resolve(host, port, **kw):
                return records('93.184.216.34', ip)
            with self.subTest(ip=ip), self.assertRaises(ValueError):
                asyncio.run(gateway.pinned_public_address(
                    'search.example.org', 443, resolve=resolve,
                ))

    def test_rebind_changes_and_invalid_answers_fail_closed(self):
        for result in ([], records('10.0.0.8'), records('93.184.216.34') * 33):
            async def resolve(host, port, **kw):
                return result
            with self.subTest(count=len(result)), self.assertRaises(ValueError):
                asyncio.run(gateway.pinned_public_address(
                    'search.example.org', 443, resolve=resolve,
                ))

    def test_refuse_non_https_ports_before_dns_lookup(self):
        resolver = AsyncMock()
        for port in (0, 80, 444, 8080, 65535):
            with self.subTest(port=port), self.assertRaises(ValueError):
                asyncio.run(gateway.pinned_public_address(
                    'search.example.org', port, resolve=resolver,
                ))
        resolver.assert_not_awaited()

    def test_dial_is_numeric_and_pinned(self):
        async def run():
            loop = asyncio.get_running_loop()
            sock = Mock()
            connect = AsyncMock()
            open_connection = AsyncMock(return_value=(object(), object()))
            with patch('socket.socket', return_value=sock):
                with patch.object(loop, 'sock_connect', connect):
                    with patch('asyncio.open_connection', open_connection):
                        await gateway.open_pinned_target(
                            socket.AF_INET, '93.184.216.34', 443,
                        )
            connect.assert_awaited_once_with(sock, ('93.184.216.34', 443))
            self.assertEqual((), open_connection.await_args.args)
            self.assertIs(sock, open_connection.await_args.kwargs['sock'])
            self.assertNotIn('host', open_connection.await_args.kwargs)
        asyncio.run(run())

    def test_socks_rejects_unsafe_dns_before_dial(self):
        async def run():
            reader = asyncio.StreamReader()
            host = b'search.example.org'
            data = b'\x05\x01\x00\x05\x01\x00\x03' + bytes([len(host)]) + host + struct.pack('!H', 443)
            reader.feed_data(data)
            reader.feed_eof()
            writer = Mock()
            writer.drain = AsyncMock()
            writer.wait_closed = AsyncMock()
            with patch.object(gateway, 'pinned_public_address', new_callable=AsyncMock,
                              side_effect=ValueError('synthetic private target')) as resolve:
                with patch.object(gateway, 'open_pinned_target', new_callable=AsyncMock) as dial:
                    await gateway.handle_connection(reader, writer)
                    resolve.assert_awaited_once()
                    dial.assert_not_awaited()
            chunks = [call.args[0] for call in writer.write.call_args_list]
            self.assertEqual(b'\x05\x00', chunks[0])
            self.assertEqual(b'\x05\x04', chunks[-1][:2])
        asyncio.run(run())

    def test_authorized_dns_pinned_tunnel_relays_bytes_without_new_lookup(self):
        async def run():
            reader = asyncio.StreamReader()
            host = b'search.example.org'
            handshake = (
                b'\x05\x01\x00\x05\x01\x00\x03'
                + bytes([len(host)]) + host + struct.pack('!H', 443)
            )
            reader.feed_data(handshake + b'client-synthetic-payload')
            reader.feed_eof()
            writer = Mock()
            writer.drain = AsyncMock()
            writer.wait_closed = AsyncMock()
            writer.can_write_eof.return_value = True

            peer_reader = asyncio.StreamReader()
            peer_reader.feed_data(b'provider-synthetic-payload')
            peer_reader.feed_eof()
            peer_writer = Mock()
            peer_writer.drain = AsyncMock()
            peer_writer.wait_closed = AsyncMock()
            peer_writer.can_write_eof.return_value = True

            with patch.object(gateway, 'pinned_public_address',
                              new_callable=AsyncMock,
                              return_value=(socket.AF_INET, '93.184.216.34')) as dns:
                with patch.object(gateway, 'open_pinned_target',
                                  new_callable=AsyncMock,
                                  return_value=(peer_reader, peer_writer)) as dial:
                    await gateway.handle_connection(reader, writer)
                    dns.assert_awaited_once_with('search.example.org', 443)
                    dial.assert_awaited_once_with(socket.AF_INET, '93.184.216.34', 443)

            sent = [call.args[0] for call in writer.write.call_args_list]
            forwarded = [call.args[0] for call in peer_writer.write.call_args_list]
            self.assertEqual(b'\x05\x00', sent[0])
            self.assertIn(b'\x05\x00\x00\x01', sent[1])
            self.assertIn(b'provider-synthetic-payload', sent)
            self.assertIn(b'client-synthetic-payload', forwarded)
            self.assertFalse(any(chunk[:2] == b'\x05\x04' for chunk in sent))
            peer_writer.close.assert_called_once()
            writer.close.assert_called_once()
        asyncio.run(run())

    def test_ip_literal_socks_request_never_resolves_or_dials(self):
        async def run():
            reader = asyncio.StreamReader()
            reader.feed_data(
                b'\x05\x01\x00\x05\x01\x00\x01'
                + socket.inet_aton('127.0.0.1') + struct.pack('!H', 443)
            )
            reader.feed_eof()
            writer = Mock()
            writer.drain = AsyncMock()
            writer.wait_closed = AsyncMock()
            with patch.object(gateway, 'pinned_public_address', new_callable=AsyncMock) as resolve:
                await gateway.handle_connection(reader, writer)
                resolve.assert_not_awaited()
            self.assertTrue(any(
                x.args[0][:2] == b'\x05\x08' for x in writer.write.call_args_list
            ))
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
