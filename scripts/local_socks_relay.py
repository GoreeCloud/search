#!/usr/bin/env python3
"""Staging-only byte relay from local SOCKS5H to the private-network Tor service.

The application keeps its approved 127.0.0.1 SOCKS5H contract. This process
cannot choose external destinations: it forwards all bytes to a fixed Tor
service on the internal Docker bridge, which handles SOCKS and remote DNS.
No request bytes, domains, client identifiers, or errors are logged.
"""
from __future__ import annotations

import asyncio

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 9050
TOR_HOST = "tor"
TOR_PORT = 9050
CONNECT_TIMEOUT = 5


async def copy_stream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(16384):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        writer.close()


async def relay(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    try:
        tor_reader, tor_writer = await asyncio.wait_for(
            asyncio.open_connection(TOR_HOST, TOR_PORT),
            timeout=CONNECT_TIMEOUT,
        )
    except (OSError, asyncio.TimeoutError):
        client_writer.close()
        await client_writer.wait_closed()
        return

    tasks = [
        asyncio.create_task(copy_stream(client_reader, tor_writer)),
        asyncio.create_task(copy_stream(tor_reader, client_writer)),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        tor_writer.close()
        client_writer.close()
        await asyncio.gather(
            tor_writer.wait_closed(), client_writer.wait_closed(),
            return_exceptions=True,
        )


async def main() -> None:
    server = await asyncio.start_server(relay, LOCAL_HOST, LOCAL_PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
