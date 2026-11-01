"""Enforce distinct free-search canary and immutable live Caddy separation."""
from pathlib import Path
import unittest

import yaml

ROOT=Path(__file__).resolve().parents[2]
CANARY=ROOT/"deploy/vps/compose.free-metasearch-canary.yaml"
FREE_SETTINGS=ROOT/"configs/goreecloud/settings.free-first.yml"
EXISTING_ROUTE=ROOT/"deploy/vps/Caddyfile.search"


class FreeCanaryReleaseContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=yaml.safe_load(CANARY.read_text(encoding="utf-8"))
        cls.services=cls.d["services"]
        cls.settings=yaml.safe_load(FREE_SETTINGS.read_text(encoding="utf-8"))

    def test_exact_distinct_name_and_no_live_network_sharing_with_search(self):
        self.assertEqual("goreecloud-search-free-canary", self.d["name"])
        self.assertEqual({"search", "ingress"}, set(self.services))
        self.assertEqual({"provider_egress", "app_link"},set(self.services["search"]["networks"]))
        self.assertEqual({"app_link", "private_ingress"},set(self.services["ingress"]["networks"]))
        self.assertEqual("proxy",self.d["networks"]["private_ingress"]["name"])
        self.assertTrue(self.d["networks"]["private_ingress"]["external"])
        self.assertTrue(self.d["networks"]["app_link"]["internal"])
        self.assertFalse(self.d["networks"]["provider_egress"]["internal"])
        self.assertFalse(self.d["networks"]["provider_egress"]["enable_ipv6"])

    def test_unique_canary_alias_no_override_of_existing_caddy_upstream(self):
        self.assertEqual(
            ["goreecloud-search-free-canary-gateway"],
            self.services["ingress"]["networks"]["private_ingress"]["aliases"],
        )
        old=EXISTING_ROUTE.read_text(encoding="utf-8")
        self.assertIn("reverse_proxy goreecloud-search-gateway:8080",old)
        self.assertNotIn("goreecloud-search-free-canary-gateway",old)
        self.assertNotIn("goreecloud-search-gateway",CANARY.read_text())

    def test_health_first_reverse_proxy_and_restart_recovery(self):
        search=self.services["search"]
        ingress=self.services["ingress"]
        self.assertIn("/readyz"," ".join(search["healthcheck"]["test"]))
        self.assertEqual({"search":{"condition":"service_healthy"}},ingress["depends_on"])
        self.assertEqual("unless-stopped",search["restart"])
        self.assertEqual("unless-stopped",ingress["restart"])
        self.assertEqual("1",search["environment"]["GRANIAN_WORKERS"])

    def test_no_public_bindings_and_separate_storage(self):
        for name,service in self.services.items():
            with self.subTest(name=name):
                self.assertNotIn("ports",service)
                self.assertEqual("977:977",service["user"])
                self.assertTrue(service["read_only"])
                self.assertIn("ALL",service["cap_drop"])
                self.assertIn("no-new-privileges:true",service["security_opt"])
                self.assertGreater(service["mem_limit"].rstrip("m").isdigit(),False)
        search=self.services["search"]
        self.assertTrue(any("settings.free-first.yml" in x for x in search["volumes"]))
        self.assertNotIn("search-cache",str(self.services))
        self.assertNotIn("private-settings.yml",str(self.services))

    def test_no_commercial_api_or_tor_dependency(self):
        self.assertFalse(self.settings["goreecloud"]["require_anonymous_egress"])
        self.assertFalse(self.settings["outgoing"]["using_tor_proxy"])
        self.assertEqual({},self.settings["outgoing"]["proxies"])
        self.assertEqual(12,self.settings["goreecloud"]["request_budget_per_minute"])
        engines=self.settings["use_default_settings"]["engines"]["keep_only"]
        self.assertNotIn("braveapi",engines)
        self.assertNotIn("exaapi",engines)
        self.assertNotIn("tor",self.services)
        self.assertNotIn("relay",self.services)

    def test_private_host_is_pinned(self):
        self.assertEqual("search-dev.goreecloud.com",
                         self.services["search"]["environment"]["GOREECLOUD_SEARCH_PRIVATE_HOST"])
        self.assertNotIn("SEARXNG_PUBLIC_INSTANCE",self.services["search"]["environment"])


if __name__=="__main__":
    unittest.main()
