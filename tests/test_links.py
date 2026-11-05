"""Offline public-navigation link policy contracts for every Search source."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from goreecloud_search.links import public_https_url
from goreecloud_search.providers import _public_https, normalize
from goreecloud_search.store import InvalidDocument, import_jsonl, initialize, safe_url, search


class PublicLinkPolicyTests(unittest.TestCase):
    def test_safe_public_urls_preserve_original_navigation_link(self):
        candidates = (
            "https://example.org/guide?q=privacy#section",
            "https://www.example.com:443/path",
            "https://münich.example.org/notebook",
            "https://[2606:4700:4700::1111]/",
        )
        for url in candidates:
            with self.subTest(url=url):
                self.assertEqual(public_https_url(url), url)
                self.assertEqual(safe_url(url), url)
                self.assertEqual(_public_https(url), url)

    def test_private_special_use_domains_and_single_labels_refused(self):
        candidates = (
            "https://localhost/", "https://localhost./",
            "https://intranet/", "https://host.local/",
            "https://workstation.lan/", "https://host.internal/",
            "https://host.test/", "https://host.invalid/",
            "https://host.example/", "https://router.home.arpa/",
            "https://service.onion/", "https://network.alt/",
        )
        for url in candidates:
            with self.subTest(url=url):
                self.assertIsNone(public_https_url(url))
                self.assertIsNone(_public_https(url))
                with self.assertRaises(InvalidDocument):
                    safe_url(url)

    def test_localdomain_namespace_is_not_a_public_navigation_target(self):
        # Common local resolver domains must not become trusted public results.
        candidates = (
            "https://router.localdomain/admin",
            "https://nested.router.localdomain/",
            "https://localhost.localdomain/",
            "https://router.ｌｏｃａｌｄｏｍａｉｎ/",
            "https://nested.router.localdomain./",
        )
        for url in candidates:
            with self.subTest(url=url):
                self.assertIsNone(public_https_url(url))
                self.assertIsNone(_public_https(url))
                with self.assertRaises(InvalidDocument):
                    safe_url(url)

    def test_unicode_idna_compatibility_cannot_bypass_local_domains(self):
        candidates = (
            "https://router.ｌｏｃａｌ/",
            "https://server.ＴＥＳＴ/",
            "https://unit.ｉｎｔｅｒｎａｌ/",
            "https://host.ｌａｎ/",
            "https://ｌｏｃａｌｈｏｓｔ/",
            "https://host.ｅｘａｍｐｌｅ/",
            "https://router.ｈｏｍｅ.ａｒｐａ/",
            "https://hidden.ｏｎｉｏｎ/", "https://service.ａｌｔ/",
            "https://name。local/",
        )
        for url in candidates:
            with self.subTest(url=url):
                self.assertIsNone(public_https_url(url))
                self.assertIsNone(_public_https(url))
                with self.assertRaises(InvalidDocument):
                    safe_url(url)

    def test_unicode_digits_must_not_bypass_private_ip_filter(self):
        for url in (
            "https://１２７.０.０.１/",
            "https://１９２.１６８.１.１/",
            "https://１０.０.０.１/",
            "https://２１３０７０６４３３/",
        ):
            with self.subTest(url=url):
                self.assertIsNone(public_https_url(url))
                with self.assertRaises(InvalidDocument):
                    safe_url(url)

    def test_noncanonical_controls_and_backslashes_are_rejected(self):
        for url in (
            "\thttps://example.org/",
            "https://example.org/\npath",
            "https://example.org/\rpath",
            "https://example.org/\x7fpath",
            "https://example.org/path\\private",
        ):
            with self.subTest(url=repr(url)):
                self.assertIsNone(public_https_url(url))
                with self.assertRaises(InvalidDocument):
                    safe_url(url)

    def test_browser_numeric_private_hosts_are_refused(self):
        candidates = (
            "https://127.1/", "https://127.0.0.1./",
            "https://2130706433/", "https://0x7f.1/",
            "https://0177.1/", "https://[::1]/",
            "https://10.1.2.3/", "https://192.168.0.1/",
        )
        for url in candidates:
            with self.subTest(url=url):
                self.assertIsNone(public_https_url(url))
                self.assertIsNone(_public_https(url))
                with self.assertRaises(InvalidDocument):
                    safe_url(url)

    def test_malformed_or_credentialed_urls_are_refused(self):
        candidates = (
            "http://example.org/", "https://user@example.org/",
            "https://example.org:8080/", "https://invalid_host.example.org/",
            "https://-invalid.example.org/", "https://example.org\\local/",
            "https://host.123/", "https://host%25zone.example.org/",
            "javascript:alert(1)",
        )
        for url in candidates:
            with self.subTest(url=url):
                self.assertIsNone(public_https_url(url))
                with self.assertRaises(InvalidDocument):
                    safe_url(url)

    def test_result_link_policy_fails_for_invalid_input_types(self):
        for value in (None, 23, {}, [], "", "x" * 2049):
            with self.subTest(input_type=type(value).__name__):
                self.assertIsNone(public_https_url(value))
                with self.assertRaises(InvalidDocument):
                    safe_url(value)

    def test_external_provider_normalization_skips_unsafe_links(self):
        payload = {
            "web": {"results": [
                {"title": "Private", "description": "Hidden", "url": "https://127.1/path"},
                {"title": "Public", "description": "Open", "url": "https://example.org/public"},
            ]}
        }
        result = normalize(payload, "brave", 10)
        self.assertEqual([item["title"] for item in result], ["Public"])
        self.assertEqual(result[0]["url"], "https://example.org/public")

    def test_failed_import_preserves_existing_private_catalog(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            db = base / "catalog.sqlite3"
            initialize(db)
            source = base / "records.jsonl"
            good = {"title": "Original", "description": "Safe record",
                    "url": "https://example.org/docs"}
            source.write_text(json.dumps(good) + "\n", encoding="utf-8")
            import_jsonl(db, source)
            poisoned = {"title": "Internal", "description": "Local link",
                        "url": "https://127.1/admin"}
            source.write_text(json.dumps(poisoned) + "\n", encoding="utf-8")
            with self.assertRaises(InvalidDocument):
                import_jsonl(db, source)
            self.assertEqual([row["title"] for row in search(db, "safe")], ["Original"])


if __name__ == "__main__":
    unittest.main()
