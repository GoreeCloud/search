"""Offline contract: approved Web providers receive a bounded Tor deadline.

The SearXNG upstream default of 3s cannot accommodate fresh Tor attestation.
extra_proxy_timeout only applies to engines with onion_url and does not help
ordinary HTTPS providers. This test makes that limit explicit and reversible.
"""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "configs/goreecloud/settings.yml"


class TorProviderTimeoutBudgetTests(unittest.TestCase):
    def test_private_tor_profile_has_bounded_request_timeout(self):
        settings = yaml.safe_load(SETTINGS.read_text())
        outgoing = settings["outgoing"]
        self.assertIs(True, outgoing["using_tor_proxy"])
        self.assertEqual("socks5h://127.0.0.1:9050", outgoing["proxies"]["all://"])
        self.assertEqual(12.0, outgoing["request_timeout"])
        self.assertEqual(12.0, outgoing["max_request_timeout"])
        self.assertLessEqual(outgoing["max_request_timeout"], 15.0)
        self.assertIs(True, settings["goreecloud"]["require_anonymous_egress"])

    def test_no_unapproved_provider_or_global_direct_fallback(self):
        settings = yaml.safe_load(SETTINGS.read_text())
        self.assertEqual(7, settings["goreecloud"]["max_provider_fanout"])
        self.assertNotIn("http://", str(settings["outgoing"]["proxies"]))
        from searx.goreecloud_policy import SEARCH_SOURCE_FAMILIES
        self.assertEqual(
            {'brave', 'startpage', 'qwant', 'duckduckgo', 'ecosia', 'bing', 'google'},
            set(SEARCH_SOURCE_FAMILIES['general']),
        )


if __name__ == "__main__":
    unittest.main()
