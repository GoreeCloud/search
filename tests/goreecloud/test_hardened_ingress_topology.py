"""Structural contract for the separate, non-production hardened ingress candidate."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy/vps/compose.hardened-private-candidate.yaml"
CADDY = ROOT / "deploy/vps/Caddyfile.hardened-ingress"


class HardenedIngressContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
        cls.services = cls.cfg["services"]

    def test_private_search_has_no_default_route_attachment_or_host_port(self):
        search = self.services["search"]
        self.assertEqual({"search_internal"}, set(search["networks"]))
        self.assertEqual("0.0.0.0", search["environment"]["GRANIAN_HOST"])
        self.assertTrue(search["read_only"])
        self.assertNotIn("ports", search)
        self.assertIn("staging-start-search.py", " ".join(search["entrypoint"]))
        self.assertEqual("172.29.247.3", search["networks"]["search_internal"]["ipv4_address"])

    def test_tor_is_only_outbound_service(self):
        self.assertEqual({"search_internal", "tor_egress"}, set(self.services["tor"]["networks"]))
        self.assertEqual("172.29.247.2", self.services["tor"]["networks"]["search_internal"]["ipv4_address"])
        self.assertFalse(self.cfg["networks"]["tor_egress"]["internal"])
        self.assertTrue(self.cfg["networks"]["search_internal"]["internal"])
        self.assertFalse(self.cfg["networks"]["search_internal"]["enable_ipv6"])
        self.assertEqual("172.29.247.0/28",
                         self.cfg["networks"]["search_internal"]["ipam"]["config"][0]["subnet"])

    def test_proxy_ingress_cannot_attach_search_to_external_network(self):
        ingress = self.services["ingress"]
        self.assertEqual({"search_internal","private_ingress"},set(ingress["networks"]))
        self.assertNotIn("ports",ingress)
        self.assertTrue(ingress["read_only"])
        self.assertEqual(["NET_BIND_SERVICE"], ingress["cap_add"])
        self.assertEqual("no",str(ingress["restart"]))
        self.assertIn("goreecloud-search-hardened-gateway",
                      ingress["networks"]["private_ingress"]["aliases"])
        self.assertNotIn("goreecloud-search-gateway",
                         ingress["networks"]["private_ingress"]["aliases"])
        self.assertTrue(self.cfg["networks"]["private_ingress"]["external"])
        self.assertIn("SEARCH_CANDIDATE_INGRESS_NETWORK",
                      self.cfg["networks"]["private_ingress"]["name"])

    def test_ingress_not_open_proxy_or_query_log(self):
        text = CADDY.read_text(encoding="utf-8")
        self.assertIn("reverse_proxy search:8080",text)
        self.assertIn("header_up X-Forwarded-For 127.0.0.1",text)
        self.assertIn("no-referrer",text)
        self.assertIn("no-store",text)
        self.assertNotIn("\n    log",text)
        self.assertNotIn("forward_proxy",text)

    def test_no_container_publishes_or_uses_host_network(self):
        for name,service in self.services.items():
            with self.subTest(name=name):
                self.assertNotIn("ports",service)
                self.assertNotEqual("host",service.get("network_mode"))
                self.assertIn("ALL",service["cap_drop"])
                self.assertIn("no-new-privileges:true",service["security_opt"])


if __name__ == "__main__":
    unittest.main()
