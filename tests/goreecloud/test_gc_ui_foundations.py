"""Pinned, offline GC UI Foundations integration contract for Search."""

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "searx/static/themes/simple"
BASE = ROOT / "searx/templates/simple/base.html"
FOUNDATIONS = ASSETS / "gc-ui/css/gc.v1.generated.css"
LICENSE = ASSETS / "gc-ui/LICENSE"
FOUNDATIONS_CSS_SHA256 = "0334a004bf55470f6e99ff938b54a94f83c4765ab44b098e25af9de9d00f6d50"
FOUNDATIONS_LICENSE_SHA256 = "b1d2870f1a00e4d7f56576e5f0870cba109e041f8af66866cf5b499478e654e7"


class GCUISupportedFoundationsTests(unittest.TestCase):
    def test_official_release_css_and_license_bytes_are_unchanged(self):
        self.assertEqual(hashlib.sha256(FOUNDATIONS.read_bytes()).hexdigest(), FOUNDATIONS_CSS_SHA256)
        self.assertEqual(hashlib.sha256(LICENSE.read_bytes()).hexdigest(), FOUNDATIONS_LICENSE_SHA256)
        self.assertIn("Apache License", LICENSE.read_text(encoding="utf-8"))

    def test_foundations_css_has_expected_invariant_geometry_and_no_remote_imports(self):
        css = FOUNDATIONS.read_text(encoding="utf-8")
        for token, value in {
            "--gc-v1-foundation-radius-md": "18px",
            "--gc-v1-foundation-radius-pill": "999px",
            "--gc-v1-foundation-radius-sm": "12px",
            "--gc-v1-foundation-radius-xs": "6px",
            "--gc-v1-foundation-target-comfortable": "44px",
            "--gc-v1-component-focus-width": "3px",
            "--gc-v1-component-focus-offset": "3px",
        }.items():
            self.assertIn(f"{token}: {value};", css)
        self.assertNotRegex(css, re.compile(r"@import|url\s*\(|https?://", re.IGNORECASE))

    def test_approved_local_foundations_css_precedes_current_legacy_and_search_styles(self):
        html = BASE.read_text(encoding="utf-8")
        local = "gc-ui/css/gc.v1.generated.css"
        inherited = "glaze/css/glaze-v1.4.1.css"
        consumer = "goreecloud-search.css"
        self.assertLess(html.index(local), html.index(inherited))
        self.assertLess(html.index(inherited), html.index(consumer))
        self.assertNotIn("cdn.jsdelivr", html)

    def test_search_consumes_foundations_for_compatible_geometry_not_unverified_colors(self):
        css = (ASSETS / "goreecloud-search.css").read_text(encoding="utf-8")
        self.assertIn("var(--gc-v1-foundation-typography-family-ui", css)
        self.assertIn("var(--gc-v1-foundation-target-comfortable, 44px)", css)
        self.assertIn("var(--gc-v1-foundation-radius-md, 18px)", css)
        self.assertIn("var(--gc-v1-component-focus-width, 3px)", css)
        # Search's brand palette is retained until the separate visual gate.
        self.assertIn("--gc-accent: #087e79", css)
        self.assertNotIn("--gc-accent: var(--gc-v1-color-primary", css)


if __name__ == "__main__":
    unittest.main()
