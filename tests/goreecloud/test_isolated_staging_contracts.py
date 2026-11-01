"""Offline tests of the isolated Search/Tor staging Compose contract."""
import asyncio
import importlib.util
from ipaddress import ip_address, ip_network
from pathlib import Path
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'isolated_local_relay', ROOT / 'scripts/local_socks_relay.py'
)
RELAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELAY)


class IsolatedStagingContractTests(unittest.TestCase):
    def test_network_separation_and_no_published_ports(self):
        doc = yaml.safe_load((ROOT / "deploy/vps/compose.isolated-staging.yaml").read_text())
        self.assertEqual("goreecloud-search-isolated-staging", doc["name"])
        services = doc["services"]
        self.assertEqual(
            {"search_internal": {"ipv4_address": "172.29.247.3"}},
            services["search"]["networks"],
        )
        self.assertEqual(
            {"search_internal": {"ipv4_address": "172.29.247.2"}, "tor_egress": {}},
            services["tor"]["networks"],
        )
        inner = ip_network(doc["networks"]["search_internal"]["ipam"]["config"][0]["subnet"])
        self.assertEqual(ip_network("172.29.247.0/28"), inner)
        self.assertIn(ip_address("172.29.247.2"), inner)
        self.assertIn(ip_address("172.29.247.3"), inner)
        tor_command = services["tor"]["command"]
        self.assertEqual(
            ["accept 172.29.247.3/32", "reject *"],
            [tor_command[index + 1] for index, arg in enumerate(tor_command[:-1])
             if arg == "--SocksPolicy"],
        )
        self.assertEqual("172.29.247.2:9050", tor_command[tor_command.index("--SocksPort") + 1])
        self.assertNotIn("0.0.0.0:9050", tor_command)
        self.assertEqual("service:search", services["relay"]["network_mode"])
        self.assertIs(True, doc["networks"]["search_internal"]["internal"])
        self.assertIs(False, doc["networks"]["tor_egress"]["internal"])
        for network in doc["networks"].values():
            self.assertIs(False, network["enable_ipv6"])
        for name, svc in services.items():
            with self.subTest(name=name):
                self.assertNotIn("ports", svc)
                self.assertNotIn("extra_hosts", svc)
                self.assertIs(True, svc["read_only"])
                self.assertEqual(["ALL"], svc["cap_drop"])
                self.assertIn("no-new-privileges:true", svc["security_opt"])
                self.assertEqual("no", svc["restart"])
                self.assertTrue(all(x.endswith(":ro") for x in svc.get("volumes", [])))
        self.assertEqual("977:977", services["search"]["user"])
        self.assertEqual(
            ["/usr/local/searxng/.venv/bin/python", "-u", "/usr/local/searxng/staging-start-search.py"],
            services["search"]["entrypoint"],
        )
        self.assertIn(
            "../../scripts/staging_start_search.py:/usr/local/searxng/staging-start-search.py:ro",
            services["search"]["volumes"],
        )
        self.assertEqual("127.0.0.1", services["search"]["environment"]["GRANIAN_HOST"])
        self.assertEqual(
            "search-dev.goreecloud.com",
            services["search"]["environment"]["GOREECLOUD_SEARCH_PRIVATE_HOST"],
        )

    def test_proxy_contract_does_not_widen_to_remote_service(self):
        source = (ROOT / "scripts/local_socks_relay.py").read_text()
        self.assertIn('LOCAL_HOST = "127.0.0.1"', source)
        self.assertIn('TOR_HOST = "tor"', source)
        self.assertIn("TOR_PORT = 9050", source)
        self.assertIn(
            "socks5h://127.0.0.1:9050",
            (ROOT / "configs/goreecloud/settings.yml").read_text(),
        )


    def test_bounded_relay_close_contract(self):
        self.assertEqual(120, RELAY.SESSION_TIMEOUT)
        source = (ROOT / "scripts/local_socks_relay.py").read_text()
        self.assertIn("return_when=asyncio.ALL_COMPLETED", source)
        self.assertIn("writer.write_eof()", source)

    def test_real_asyncio_relay_passes_only_to_fixed_synthetic_gateway(self):
        async def run():
            received = []

            async def fixture_gateway(reader, writer):
                received.append(await reader.readexactly(7))
                writer.write(b"accepted")
                await writer.drain()
                writer.close()
                await writer.wait_closed()

            gateway = await asyncio.start_server(fixture_gateway, "127.0.0.1", 0)
            local = await asyncio.start_server(RELAY.relay, "127.0.0.1", 0)
            try:
                with patch.object(RELAY, "TOR_HOST", "127.0.0.1"), patch.object(
                    RELAY, "TOR_PORT", gateway.sockets[0].getsockname()[1]
                ):
                    reader, writer = await asyncio.open_connection(
                        "127.0.0.1", local.sockets[0].getsockname()[1]
                    )
                    writer.write(b"fixture")
                    await writer.drain()
                    self.assertEqual(b"accepted", await asyncio.wait_for(reader.read(16), 3))
                    writer.close()
                    await writer.wait_closed()
                self.assertEqual([b"fixture"], received)
            finally:
                gateway.close()
                local.close()
                await gateway.wait_closed()
                await local.wait_closed()

        asyncio.run(run())

    def test_missing_gateway_closes_relay_without_leaking_requests(self):
        async def run():
            async def missing(*_args, **_kwargs):
                raise OSError("synthetic unavailable gateway")

            async def local_handler(reader, writer):
                with patch.object(RELAY.asyncio, "open_connection", new=missing):
                    await RELAY.relay(reader, writer)

            local = await asyncio.start_server(local_handler, "127.0.0.1", 0)
            try:
                reader, writer = await asyncio.open_connection(
                    "127.0.0.1", local.sockets[0].getsockname()[1]
                )
                writer.write(b"synthetic")
                await writer.drain()
                # Linux/asyncio can signal denial as EOF or ECONNRESET when
                # the client has already queued bytes. Both must carry zero data.
                try:
                    denied = await asyncio.wait_for(reader.read(16), 3)
                except ConnectionResetError:
                    denied = b""
                self.assertEqual(b"", denied)
                writer.close()
                try:
                    await writer.wait_closed()
                except ConnectionResetError:
                    pass
            finally:
                local.close()
                await local.wait_closed()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
