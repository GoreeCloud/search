#!/usr/bin/env python3
"""Staging-only non-Tor SOCKS5H gateway with DNS-address pinning.

Bound to loopback only. Intended for an isolated *remote* Search network
namespace. This is not an egress firewall and is not production-ready.
No search queries, hostnames, client identities, or DNS answers are logged.
"""
import argparse
import asyncio
import ipaddress
import socket
import struct
from typing import Callable

from searx.goreecloud_policy import safe_external_media_url

GREETING_TIMEOUT = 5
DNS_TIMEOUT = 6
CONNECT_TIMEOUT = 6
SESSION_TIMEOUT = 90
MAX_CLIENTS = 24
PUBLIC_HTTPS_PORT = 443
# IPv4-over-IPv6 translation/tunnel ranges may indirectly reach IPv4
# destinations that the initial IPv6 address classification would allow.
# Exclude them rather than relying on operator-specific NAT64 rules.
IPV6_TRANSLATION_AND_TUNNELS = tuple(
    ipaddress.ip_network(cidr) for cidr in (
        '64:ff9b::/96',       # NAT64 well-known prefix (RFC 6052)
        '64:ff9b:1::/48',     # NAT64 local-use translation prefix
        '::ffff:0:0/96',      # IPv4-mapped
        '2002::/16',         # 6to4
        '2001::/32',         # Teredo
    )
)


def external_hostname(host: str) -> bool:
    """Allow only unambiguous HTTPS DNS names with no embedded credentials."""
    return (
        isinstance(host, str) and host.isascii() and host == host.strip()
        and not any(ch in host for ch in '/\\?#@:%')
        and safe_external_media_url("https://" + host)
    )


async def pinned_public_address(host: str, port: int, resolve: Callable | None = None) -> tuple[int, str]:
    """Reject the WHOLE DNS answer if any record is non-global.

    Return a numeric address to connect to, never a hostname; this removes
    DNS re-resolution between filtering and socket creation. Firewalling is
    still required to constrain *other* outbound processes and addresses.
    """
    if port != PUBLIC_HTTPS_PORT or not external_hostname(host):
        raise ValueError("blocked outbound authority")
    if resolve is None:
        resolve = asyncio.get_running_loop().getaddrinfo
    answers = await asyncio.wait_for(
        resolve(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP), DNS_TIMEOUT
    )
    if not 1 <= len(answers) <= 32:
        raise ValueError("invalid DNS answer count")
    targets: list[tuple[int, str]] = []
    for family, socktype, proto, canonname, sockaddr in answers:
        if family not in (socket.AF_INET, socket.AF_INET6) or socktype != socket.SOCK_STREAM:
            raise ValueError("unexpected DNS record")
        address = ipaddress.ip_address(sockaddr[0])
        if address.version == 4 and family != socket.AF_INET:
            raise ValueError("DNS family mismatch")
        if address.version == 6 and family != socket.AF_INET6:
            raise ValueError("DNS family mismatch")
        if not address.is_global or address.is_multicast:
            raise ValueError("nonpublic DNS target")
        if isinstance(address, ipaddress.IPv6Address) and any(
            address in network for network in IPV6_TRANSLATION_AND_TUNNELS
        ):
            raise ValueError("IPv6 translation or tunnel destination")
        targets.append((family, str(address)))
    return targets[0]


async def open_pinned_target(family: int, address: str, port: int):
    """Connect using an already-validated numeric IP, never a second DNS lookup."""
    peer = socket.socket(family, socket.SOCK_STREAM)
    peer.setblocking(False)
    try:
        if family == socket.AF_INET6:
            dest = (address, port, 0, 0)
        else:
            dest = (address, port)
        await asyncio.wait_for(asyncio.get_running_loop().sock_connect(peer, dest), CONNECT_TIMEOUT)
        return await asyncio.open_connection(sock=peer)
    except BaseException:
        peer.close()
        raise


async def _relay(source: asyncio.StreamReader, target: asyncio.StreamWriter):
    try:
        while True:
            chunk = await source.read(32768)
            if not chunk:
                break
            target.write(chunk)
            await target.drain()
    finally:
        if target.can_write_eof():
            target.write_eof()


async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer_writer = None
    tunnel_established = False
    try:
        version, methods_count = await asyncio.wait_for(reader.readexactly(2), GREETING_TIMEOUT)
        if version != 5 or not 1 <= methods_count <= 8:
            return
        methods = await asyncio.wait_for(reader.readexactly(methods_count), GREETING_TIMEOUT)
        if 0 not in methods:
            writer.write(b"\x05\xff")
            await writer.drain()
            return
        writer.write(b"\x05\x00")
        await writer.drain()

        header = await asyncio.wait_for(reader.readexactly(4), GREETING_TIMEOUT)
        if header != b"\x05\x01\x00\x03":  # CONNECT, domain only, no IP literal requests
            writer.write(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            return
        host_size = (await asyncio.wait_for(reader.readexactly(1), GREETING_TIMEOUT))[0]
        if not 1 <= host_size <= 253:
            return
        host = (await asyncio.wait_for(reader.readexactly(host_size), GREETING_TIMEOUT)).decode('ascii')
        port = struct.unpack("!H", await asyncio.wait_for(reader.readexactly(2), GREETING_TIMEOUT))[0]

        family, addr = await pinned_public_address(host, port)
        peer_reader, peer_writer = await open_pinned_target(family, addr, port)

        # Success reply binds to unspecified local address. No hostname/IP disclosures.
        writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()
        tunnel_established = True
        await asyncio.wait_for(
            asyncio.gather(_relay(reader, peer_writer), _relay(peer_reader, writer)),
            SESSION_TIMEOUT,
        )
    except (OSError, UnicodeError, ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError):
        # Generic denial: never emit hostname, resolved IP, URL, or user data.
        if not tunnel_established:
            try:
                writer.write(b"\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00")
                await writer.drain()
            except (OSError, ConnectionError):
                pass
    finally:
        if peer_writer is not None:
            peer_writer.close()
            try:
                await peer_writer.wait_closed()
            except OSError:
                pass
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass


async def limited_connection(
    limit: asyncio.Semaphore,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
):
    """Refuse excess connections without building an unbounded wait queue."""
    if limit.locked():
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        return
    async with limit:
        await handle_connection(reader, writer)


async def serve(port: int):
    if not 1024 <= port <= 65535:
        raise ValueError("staging port must be unprivileged")
    limit = asyncio.Semaphore(MAX_CLIENTS)

    async def limited_client(reader, writer):
        await limited_connection(limit, reader, writer)

    server = await asyncio.start_server(limited_client, host='127.0.0.1', port=port, backlog=32)
    async with server:
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description='Staging-only GoreeCloud non-Tor SOCKS5H gateway')
    parser.add_argument('--port', type=int, default=19050)
    args = parser.parse_args()
    asyncio.run(serve(args.port))


if __name__ == '__main__':
    main()
