"""Bounded GC UI migration for Search's private POST category navigation."""

import re
import unittest
from pathlib import Path

from scripts.gc_ui_consumer_audit import audit


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "searx/static/themes/simple/goreecloud-settings-categories.css"
FOUNDATIONS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"
TEMPLATE = ROOT / "searx/templates/simple/goreecloud_category_nav.html"
BROWSER = ROOT / "tests/goreecloud/browser_home_smoke.py"
GC = 'html[data-gc-consumer="goreecloud-search"]'
LEGACY = "html[data-glaze-consumer]"


class GCCategoryNavTests(unittest.TestCase):
    def test_all_category_rail_selectors_use_gc_consumer_including_media_states(self):
        css = CSS.read_text(encoding="utf-8")
        for selector in (
            ".goreecloud-category-tabs",
            ".goreecloud-category-form",
            ".goreecloud-category-tab",
            '.goreecloud-category-tab[aria-current="page"]',
            ".goreecloud-category-tab.unavailable",
            ".goreecloud-tab-unavailable-note",
            ".goreecloud-category-form button:hover",
            ".goreecloud-category-form button:focus-visible",
        ):
            with self.subTest(selector=selector):
                self.assertIn(GC + " body.results_endpoint " + selector, css)
                self.assertNotIn(LEGACY + " body.results_endpoint " + selector, css)
        narrow = css.split("@media (max-width: 410px)", 1)[1]
        self.assertIn(GC + " body.results_endpoint .goreecloud-category-tabs", narrow)
        self.assertIn(GC + " body.results_endpoint .goreecloud-category-tab", narrow)

    def test_supported_semantic_focus_target_color_and_forced_color_contract(self):
        css = CSS.read_text(encoding="utf-8")
        foundations = FOUNDATIONS.read_text(encoding="utf-8")
        for token in (
            "--gc-v1-foundation-target-comfortable",
            "--gc-v1-component-focus-width",
            "--gc-v1-color-focus-ring",
            "--gc-v1-color-on-surface-muted",
            "--gc-v1-color-primary",
            "--gc-v1-foundation-opacity-disabled",
        ):
            with self.subTest(token=token):
                self.assertIn(token + ":", foundations)
                self.assertIn("var(" + token, css)
        self.assertRegex(css, re.compile(r"\.goreecloud-category-form button:focus-visible\s*\{\s*outline: var\(--gc-v1-component-focus-width", re.S))
        self.assertIn("@media (forced-colors: active)", css)
        self.assertIn("outline-color: Highlight", css)
        self.assertIn("color: GrayText; opacity: 1", css)

    def test_native_post_and_source_state_are_not_replaced_with_navigation_links(self):
        nav = TEMPLATE.read_text(encoding="utf-8")
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn('method="post" class="goreecloud-category-form"', nav)
        self.assertIn('<input type="hidden" name="q" value=', nav)
        self.assertIn('<input type="hidden" name="engines" value=', nav)
        self.assertIn('<input type="hidden" name="category_{{ tab.category }}"', nav)
        self.assertIn('aria-current="page"', nav)
        self.assertIn('aria-disabled="true"', nav)
        self.assertIn("'Category switch leaked query'", browser)
        self.assertIn("categoryTargetHeights:buttons.map", browser)

    def test_measured_legacy_debt_falls_without_full_acceptance_claim(self):
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLessEqual(report["active_legacy_lines"], 377)
        self.assertFalse(report["full_gc_ui_acceptance"])


if __name__ == "__main__":
    unittest.main()
