"""Offline tests of the isolated Search/Tor staging Compose contract."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class IsolatedStagingContractTests(unittest.TestCase):
    def test_network_separation_and_no_published_ports(self):
        doc = yaml.safe_load((ROOT / "deploy/vps/compose.isolated-staging.yaml").read_text())
        self.assertEqual("goreecloud-search-isolated-staging", doc["name"])
        services = doc["services"]
        self.assertEqual(["search_internal"], services["search"]["networks"])
        self.assertEqual(["search_internal", "tor_egress"], services["tor"]["networks"])
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


if __name__ == "__main__":
    unittest.main()
