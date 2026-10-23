"""Bounded GC UI preflight acceptance: actual private POST flow and styled controls."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lxml import html

from scripts.gc_ui_consumer_audit import audit
from gc_ui_preview_offline import offline_preview_app


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "searx/static/themes/simple/goreecloud-search.css"
FOUNDATIONS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"
BROWSER = ROOT / "tests/goreecloud/browser_preview_smoke.py"
GC = 'html[data-gc-consumer="goreecloud-search"]'
LEGACY = 'html[data-glaze-consumer]'


class SyntheticPreviewContinuation:
    """Actual form parsing and results rendering, zero external provider calls."""

    def __init__(self, search_query, *args):
        self.search_query = search_query

    def search(self):
        return SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )


class GCUISearchPreviewTests(unittest.TestCase):
    headers = {"X-Real-IP": "127.0.0.1"}

    def test_preflight_css_uses_gc_consumer_for_real_controls(self):
        css = CSS.read_text(encoding="utf-8")
        migrated = css.split("/* Source preflight:", 1)[1].split("/* Per-result-page", 1)[0]
        self.assertNotIn(LEGACY, migrated)
        for suffix in (
            ".goreecloud-preview-trigger {",
            ".goreecloud-preview {",
            ".goreecloud-preview-continue {",
            ".goreecloud-preview summary {",
            ".goreecloud-preview-single form {",
            ".goreecloud-preview-single select {",
        ):
            self.assertIn(GC + " " + suffix, migrated)
        self.assertIn("@media (max-width: 540px)", migrated)
        self.assertIn("@media (forced-colors: active)", migrated)
        self.assertIn("overflow-wrap: anywhere", migrated)
        self.assertIn("width: min(53rem, calc(100% - 1.5rem))", migrated)

    def test_pinned_token_and_accessibility_contract(self):
        css = CSS.read_text(encoding="utf-8")
        foundations = FOUNDATIONS.read_text(encoding="utf-8")
        migrated = css.split("/* Source preflight:", 1)[1].split("/* Per-result-page", 1)[0]
        for token in (
            "--gc-v1-component-button-height-medium",
            "--gc-v1-component-field-height",
            "--gc-v1-foundation-target-comfortable",
            "--gc-v1-foundation-radius-sm",
            "--gc-v1-color-surface",
            "--gc-v1-color-on-surface",
            "--gc-v1-color-outline",
            "--gc-v1-color-primary",
            "--gc-v1-color-on-primary",
            "--gc-v1-color-focus-ring",
            "--gc-v1-component-focus-width",
            "--gc-v1-component-focus-offset",
        ):
            self.assertIn(token + ":", foundations, token)
            self.assertIn("var(" + token, migrated, token)
        self.assertIn(".goreecloud-preview :is(summary, select, .goreecloud-preview-continue):focus-visible", migrated)
        self.assertIn("outline-color: Highlight;", migrated)

    def test_real_preview_has_accessible_native_post_selection_with_no_egress(self):
        with offline_preview_app().test_client() as client, patch("searx.search.SearchWithPlugins") as egress:
            response = client.post("/preview", data={
                "q": "local synthetic preview", "category_general": "1",
                "language": "en", "safesearch": "2",
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertIn("no-store", response.headers["Cache-Control"])
            page = html.fromstring(response.data)
            self.assertEqual("goreecloud-search", page.xpath("//html/@data-gc-consumer")[0])
            panel = page.xpath('//section[contains(concat(" ", normalize-space(@class), " "), " goreecloud-preview ")]')
            self.assertEqual(1, len(panel))
            self.assertEqual("preview-heading", panel[0].get("aria-labelledby"))
            self.assertEqual(1, len(panel[0].xpath('.//h1[@id="preview-heading"]')))
            self.assertEqual(1, len(panel[0].xpath('.//p[@role="status"]')))
            self.assertEqual(1, len(panel[0].xpath('.//details[@open]/summary')))
            self.assertEqual(1, len(panel[0].xpath('.//details[@class="goreecloud-preview-single"]/summary')))
            forms = panel[0].xpath('.//form[@method="post" and @action="/search"]')
            self.assertEqual(2, len(forms))
            for form in forms:
                self.assertEqual(1, len(form.xpath('.//button[@type="submit" and contains(@class,"goreecloud-preview-continue")]')))
                self.assertEqual(["local synthetic preview"], form.xpath('.//input[@name="q"]/@value'))
                self.assertEqual(["en"], form.xpath('.//input[@name="language"]/@value'))
                self.assertEqual(["2"], form.xpath('.//input[@name="safesearch"]/@value'))
            self.assertEqual(["1"], forms[0].xpath('.//input[@name="category_general"]/@value'))
            self.assertFalse(forms[1].xpath('.//input[starts-with(@name,"category_")]'))
            selects = forms[1].xpath('.//select[@id="goreecloud-provider-choice" and @name="engines" and @required]')
            self.assertEqual(1, len(selects))
            self.assertEqual(1, len(forms[1].xpath('.//label[@for="goreecloud-provider-choice"]')))
            self.assertGreaterEqual(len(selects[0].xpath('./option[@value!=""]')), 2)
            egress.assert_not_called()
            response.close()

    def test_single_source_continue_uses_actual_private_post_without_fallback(self):
        with offline_preview_app().test_client() as client:
            preview = client.post("/preview", data={
                "q": "synthetic one-source UI acceptance", "category_general": "1",
                "language": "en", "safesearch": "2",
            }, headers=self.headers)
            self.assertEqual(200, preview.status_code)
            panel = html.fromstring(preview.data)
            single_form = panel.xpath('//details[@class="goreecloud-preview-single"]/form')[0]
            source = single_form.xpath('.//select[@name="engines"]/option[@value!=""]/@value')[0]
            inputs = {node.get("name"): node.get("value") for node in single_form.xpath('.//input')}
            inputs["engines"] = source
            self.assertNotIn("category_general", inputs)
            preview.close()
            with patch("searx.search.SearchWithPlugins", SyntheticPreviewContinuation):
                result = client.post("/search", data=inputs, headers=self.headers)
                self.assertEqual(200, result.status_code)
                self.assertIn("no-store", result.headers["Cache-Control"])
                self.assertIn(b"goreecloud-source-diagnostics", result.data)
                self.assertNotIn("Location", result.headers)
                result.close()

    def test_browser_regression_covers_real_pointer_touch_keyboard_and_forced_colors(self):
        browser = BROWSER.read_text(encoding="utf-8")
        for evidence in (
            "Keys.ENTER", "Keys.TAB", "matchMedia", "setEmulatedMedia",
            "getBoundingClientRect", "--gc-v1-color-primary",
            "320, 760", "390, 844", "1440, 900", "network.assert_not_called()",
            "elementFromPoint", "scrollingElement", "target.click()",
            "Input.dispatchTouchEvent", "hitWithinTarget", "WebDriverWait",
        ):
            self.assertIn(evidence, browser)

    def test_gc_ui_debt_goes_down_without_certifying_full_acceptance(self):
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLess(report["active_legacy_lines"], 356)
        self.assertFalse(report["full_gc_ui_acceptance"])


if __name__ == "__main__":
    unittest.main()
