"""Offline regression: free upgrade cannot shadow the active search gateway."""
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[2]
UPGRADE=ROOT/"deploy/vps/compose.free-metasearch-upgrade.yaml"
LIVE=ROOT/"deploy/vps/compose.free-metasearch-canary.yaml"
SETTINGS=ROOT/"configs/goreecloud/settings.free-first.yml"

class UpgradeIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upgrade=yaml.safe_load(UPGRADE.read_text())
        cls.live=yaml.safe_load(LIVE.read_text())
        cls.settings=yaml.safe_load(SETTINGS.read_text())

    def test_project_and_gateway_are_distinct_from_live_and_rollback(self):
        new=self.upgrade
        existing=self.live
        self.assertEqual("goreecloud-search-free-upgrade",new["name"])
        self.assertEqual("goreecloud-search-free-canary",existing["name"])
        alias=new["services"]["ingress"]["networks"]["private_ingress"]["aliases"]
        live_alias=existing["services"]["ingress"]["networks"]["private_ingress"]["aliases"]
        self.assertEqual(["goreecloud-search-free-upgrade-gateway"],alias)
        self.assertTrue(set(alias).isdisjoint(live_alias))
        self.assertNotIn("goreecloud-search-gateway",str(alias))

    def test_never_exposes_search_service_on_front_network(self):
        services=self.upgrade["services"]
        self.assertEqual({"search","ingress"},set(services))
        self.assertEqual({"provider_egress","app_link"},set(services["search"]["networks"]))
        self.assertEqual({"app_link","private_ingress"},set(services["ingress"]["networks"]))
        self.assertTrue(self.upgrade["networks"]["app_link"]["internal"])
        self.assertFalse(self.upgrade["networks"]["provider_egress"]["internal"])
        self.assertFalse(self.upgrade["networks"]["provider_egress"]["enable_ipv6"])
        self.assertEqual("proxy",self.upgrade["networks"]["private_ingress"]["name"])
        self.assertTrue(self.upgrade["networks"]["private_ingress"]["external"])

    def test_no_paid_api_tor_public_ports_or_live_data_mounts(self):
        for name,service in self.upgrade["services"].items():
            with self.subTest(name=name):
                self.assertNotIn("ports",service)
                self.assertTrue(service["read_only"])
                self.assertIn("ALL",service["cap_drop"])
                self.assertIn("no-new-privileges:true",service["security_opt"])
        self.assertFalse(self.settings["goreecloud"]["require_anonymous_egress"])
        self.assertEqual(12,self.settings["goreecloud"]["request_budget_per_minute"])
        self.assertEqual({},self.settings["outgoing"]["proxies"])
        self.assertNotIn("braveapi",self.settings["use_default_settings"]["engines"]["keep_only"])
        self.assertNotIn("exaapi",self.settings["use_default_settings"]["engines"]["keep_only"])
        self.assertNotIn("search-cache",str(self.upgrade["services"]))
        self.assertNotIn("tor",self.upgrade["services"])

    def test_health_and_worker_budget_before_ingress(self):
        search=self.upgrade["services"]["search"]
        ingress=self.upgrade["services"]["ingress"]
        self.assertEqual("1",search["environment"]["GRANIAN_WORKERS"])
        self.assertIn("/readyz"," ".join(search["healthcheck"]["test"]))
        self.assertEqual({"search":{"condition":"service_healthy"}},ingress["depends_on"])
        self.assertEqual("unless-stopped",search["restart"])
        self.assertEqual("unless-stopped",ingress["restart"])

    def test_runtime_diff_only_identity_from_existing_canary(self):
        new=self.upgrade
        old=self.live
        self.assertEqual(set(new["services"]),set(old["services"]))
        self.assertEqual(new["services"]["search"],old["services"]["search"])
        new_ingress=dict(new["services"]["ingress"])
        old_ingress=dict(old["services"]["ingress"])
        new_ingress.pop("networks")
        old_ingress.pop("networks")
        self.assertEqual(new_ingress,old_ingress)

if __name__=="__main__":
    unittest.main()
