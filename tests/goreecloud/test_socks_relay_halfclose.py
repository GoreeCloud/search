"""End-to-end, offline TCP regressions for the staging-only SOCKS relay.

All sockets bind ephemeral 127.0.0.1 ports. No Tor service, external provider,
DNS lookup, query content, or production configuration is required.
"""
import asyncio
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "search_staging_socks_relay", ROOT / "scripts/local_socks_relay.py"
)
RELAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELAY)


class SocksRelayHalfCloseTests(unittest.IsolatedAsyncioTestCase):
    async def test_delayed_gateway_reply_survives_client_write_eof(self):
        received = []

        async def gateway_handler(reader, writer):
            try:
                # The remote peer cannot respond until client EOF arrives.
                received.append(await reader.read())
                await asyncio.sleep(0.06)
                writer.write(b"delayed-synthetic-reply")
                await writer.drain()
                if writer.can_write_eof():
                    writer.write_eof()
            finally:
                writer.close()
                await writer.wait_closed()

        gateway = await asyncio.start_server(gateway_handler, "127.0.0.1", 0)
        relay = await asyncio.start_server(RELAY.relay, "127.0.0.1", 0)
        try:
            with patch.object(RELAY, "TOR_HOST", "127.0.0.1"), patch.object(
                RELAY, "TOR_PORT", gateway.sockets[0].getsockname()[1]
            ):
                reader, writer = await asyncio.open_connection(
                    "127.0.0.1", relay.sockets[0].getsockname()[1]
                )
                try:
                    writer.write(b"synthetic-request")
                    await writer.drain()
                    self.assertTrue(writer.can_write_eof())
                    writer.write_eof()
                    self.assertEqual(
                        b"delayed-synthetic-reply",
                        await asyncio.wait_for(reader.read(), timeout=2),
                    )
                    self.assertEqual([b"synthetic-request"], received)
                finally:
                    writer.close()
                    await writer.wait_closed()
        finally:
            relay.close()
            gateway.close()
            await asyncio.gather(relay.wait_closed(), gateway.wait_closed())

    async def test_idle_half_closed_session_expires_and_closes_client(self):
        gateway_closed = asyncio.Event()

        async def gateway_handler(reader, writer):
            try:
                await reader.read()  # Wait for forwarded client FIN.
                await reader.read(1)  # Simulate a nonresponsive upstream.
                await asyncio.sleep(0.5)
            finally:
                writer.close()
                await writer.wait_closed()
                gateway_closed.set()

        gateway = await asyncio.start_server(gateway_handler, "127.0.0.1", 0)
        relay = await asyncio.start_server(RELAY.relay, "127.0.0.1", 0)
        try:
            with patch.object(RELAY, "TOR_HOST", "127.0.0.1"), patch.object(
                RELAY, "TOR_PORT", gateway.sockets[0].getsockname()[1]
            ), patch.object(RELAY, "SESSION_TIMEOUT", 0.05):
                reader, writer = await asyncio.open_connection(
                    "127.0.0.1", relay.sockets[0].getsockname()[1]
                )
                try:
                    writer.write_eof()
                    self.assertEqual(b"", await asyncio.wait_for(reader.read(), 1))
                finally:
                    writer.close()
                    await writer.wait_closed()
        finally:
            relay.close()
            gateway.close()
            await asyncio.gather(relay.wait_closed(), gateway.wait_closed())
            await asyncio.wait_for(gateway_closed.wait(), 2)


if __name__ == "__main__":
    unittest.main()
