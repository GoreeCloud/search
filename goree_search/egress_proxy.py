"""Minimal loopback HTTPS CONNECT proxy with DNS-to-connection IP binding.

This proxy accepts only explicitly allowlisted DNS hostnames on port 443.
It resolves once, denies non-global answers, and dials that *IP address*.
The TLS handshake remains end-to-end between Scrapy and the remote hostname.
Not a replacement for operating-system egress isolation or a production proxy.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import ipaddress
from queue import Queue
import socket
import threading

from .security import normalize_url

MAX_HEADERS = 8192
MAX_TUNNEL_BYTES = 4 * 1024 * 1024
IDLE_TIMEOUT = 30


def connect_host(target: str, allowed_hosts: set[str]) -> str:
    """Validate a CONNECT authority, returning a normalized approved hostname."""
    if target.count(":") != 1:
        raise ValueError("CONNECT requires an exact hostname:443")
    host, port = target.rsplit(":", 1)
    if port != "443" or not host or "/" in host or "@" in host:
        raise ValueError("Only HTTPS on port 443 is supported")
    normalized = normalize_url("https://" + host + "/")
    dns_host = normalized.split("/")[2]
    if dns_host not in allowed_hosts:
        raise ValueError("Hostname is not allowlisted")
    return dns_host


def select_global_address(records: list[tuple]) -> tuple[str, int]:
    """Reject the entire DNS response if any answer is private or malformed."""
    if not records:
        raise ValueError("Host has no DNS answers")
    validated = []
    for item in records:
        address = item[4][0].split("%")[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("Invalid DNS address") from exc
        if not ip.is_global:
            raise ValueError("Host DNS returned a non-global address")
        validated.append((address, item[0]))
    return validated[0]


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    transferred = 0
    try:
        while transferred < MAX_TUNNEL_BYTES:
            data = await asyncio.wait_for(
                reader.read(min(65536, MAX_TUNNEL_BYTES - transferred)), IDLE_TIMEOUT
            )
            if not data:
                break
            transferred += len(data)
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError, asyncio.TimeoutError):
        pass
    finally:
        if writer.can_write_eof():
            try:
                writer.write_eof()
            except OSError:
                pass


class EgressProxy:
    def __init__(self, allowed_hosts: set[str]):
        if not allowed_hosts:
            raise ValueError("A nonempty allowlist is required")
        self.allowed_hosts = allowed_hosts
        self._slots = asyncio.Semaphore(8)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream = None
        try:
            async with self._slots:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
                if len(head) > MAX_HEADERS:
                    raise ValueError("Oversized proxy request")
                line = head.split(b"\r\n", 1)[0].decode("ascii", "strict")
                parts = line.split(" ")
                if len(parts) != 3 or parts[0] != "CONNECT" or parts[2] != "HTTP/1.1":
                    raise ValueError("Only CONNECT over HTTP/1.1 is supported")
                host = connect_host(parts[1], self.allowed_hosts)
                infos = await asyncio.wait_for(
                    asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM),
                    5,
                )
                address, family = select_global_address(infos)
                # The validated IP, not the DNS hostname, is given to connect().
                upstream_reader, upstream = await asyncio.wait_for(
                    asyncio.open_connection(address, 443, family=family), 10
                )
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                a = asyncio.create_task(_pipe(reader, upstream))
                b = asyncio.create_task(_pipe(upstream_reader, writer))
                await asyncio.gather(a, b)
        except (ValueError, UnicodeError, asyncio.IncompleteReadError,
                asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError, OSError):
            try:
                writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await writer.drain()
            except (ConnectionError, OSError):
                pass
        finally:
            if upstream is not None:
                upstream.close()
                try:
                    await upstream.wait_closed()
                except OSError:
                    pass
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass


@contextmanager
def local_https_proxy(allowed_hosts: set[str]):
    """Start a localhost-only tunnel within the crawl command lifetime."""
    out: Queue[object] = Queue(maxsize=1)
    loop = asyncio.new_event_loop()

    def run() -> None:
        asyncio.set_event_loop(loop)
        try:
            server = loop.run_until_complete(
                asyncio.start_server(EgressProxy(allowed_hosts).handle, "127.0.0.1", 0)
            )
            out.put(server.sockets[0].getsockname()[1])
            try:
                loop.run_forever()
            finally:
                server.close()
                loop.run_until_complete(server.wait_closed())
        except Exception as exc:
            out.put(exc)
        finally:
            loop.close()

    thread = threading.Thread(target=run, name="goree-search-egress", daemon=True)
    thread.start()
    port = out.get(timeout=6)
    if isinstance(port, BaseException):
        raise RuntimeError("Unable to start loopback HTTPS proxy") from port
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=8)
