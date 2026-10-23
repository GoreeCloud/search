"""Offline contract for the next bounded GC UI Search controls migration."""

import unittest
from pathlib import Path

from scripts.gc_ui_consumer_audit import audit


ROOT = Path(__file__).resolve().parents[2]
MOCKUP = ROOT / "searx/static/themes/simple/goreecloud-mockup.css"
SHARED = ROOT / "searx/static/themes/simple/goreecloud-search.css"
FOUNDATIONS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"
FORM = ROOT / "searx/templates/simple/search.html"
BROWSER = ROOT / "tests/goreecloud/browser_home_smoke.py"
GC = 'html[data-gc-consumer="goreecloud-search"]'
LEGACY = 'html[data-glaze-consumer]'


class GCUISearchControlTests(unittest.TestCase):
    def test_home_and_results_controls_use_new_consumer_not_retired_attribute(self):
        css = MOCKUP.read_text(encoding="utf-8")
        for suffix in (
            "#main_index .goreecloud-hero .search_box",
            "#main_index .goreecloud-hero #q",
            "#main_index .goreecloud-hero #send_search",
            "#main_index .goreecloud-hero #clear_search",
            "body.results_endpoint #main_results .search_box",
            "body.results_endpoint #main_results #q",
            "body.results_endpoint #main_results #send_search",
            "body.results_endpoint #main_results #clear_search",
        ):
            self.assertIn(GC + " " + suffix, css, suffix)
            self.assertNotIn(LEGACY + " " + suffix, css, suffix)

        shared = SHARED.read_text(encoding="utf-8")
        for suffix in (".search_box", ".search_box #q", "#send_search"):
            self.assertIn(GC + " " + suffix, shared)
            self.assertNotIn(LEGACY + " " + suffix, shared)

    def test_focus_target_sizes_and_semantic_color_tokens(self):
        official = FOUNDATIONS.read_text(encoding="utf-8")
        shared = SHARED.read_text(encoding="utf-8")
        mockup = MOCKUP.read_text(encoding="utf-8")
        for token in (
            "--gc-v1-component-field-height",
            "--gc-v1-component-button-height-medium",
            "--gc-v1-foundation-target-comfortable",
            "--gc-v1-component-focus-width",
            "--gc-v1-component-focus-offset",
            "--gc-v1-color-focus-ring",
            "--gc-v1-color-on-surface-muted",
        ):
            self.assertIn(token + ":", official, token)
            self.assertIn("var(" + token, shared + mockup, token)
        self.assertIn(GC + " .search_box:focus-within", shared)
        self.assertIn(GC + " .search_box #clear_search:focus-visible", shared)
        self.assertIn(GC + " #send_search:focus-visible", shared)
        self.assertIn("width: var(--gc-v1-foundation-target-comfortable, 44px)", shared)
        self.assertIn("#q::placeholder { color: var(--gc-v1-color-on-surface-muted", mockup)
        self.assertIn("#send_search { width: 46px; height: 48px; }", mockup)

    def test_forced_colors_cover_both_search_surfaces(self):
        css = MOCKUP.read_text(encoding="utf-8")
        shared = SHARED.read_text(encoding="utf-8")
        self.assertIn("@media (forced-colors: active)", css)
        self.assertIn("@media (forced-colors: active)", shared)
        self.assertIn(GC + " .search_box:focus-within { outline-color: Highlight; }", shared)
        self.assertIn(GC + " #send_search:focus-visible { outline-color: Highlight; }", shared)
        self.assertIn(GC + " body.results_endpoint #main_results .search_box {\n    background: Canvas;", css)
        self.assertIn(GC + " body.results_endpoint #main_results #send_search {\n    background: ButtonFace;", css)

    def test_native_private_form_and_ci_browser_checks(self):
        form = FORM.read_text(encoding="utf-8")
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn('method="{{ method }}"', form)
        self.assertIn('role="search"', form)
        self.assertIn('<label class="goreecloud-visually-hidden" for="q">', form)
        self.assertIn('id="clear_search" type="reset" aria-label=', form)
        self.assertIn('id="send_search" type="submit"', form)
        self.assertIn("def assert_gc_search_controls(", browser)
        self.assertIn("def assert_gc_search_forced_colors(", browser)
        self.assertIn("'forced-colors', 'value': 'active'", browser)
        self.assertIn("assert_gc_search_controls(driver, 'results-phone')", browser)

    def test_legacy_debt_decreases_without_qualifying_the_consumer(self):
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLessEqual(report["active_legacy_lines"], 406)
        self.assertFalse(report["full_gc_ui_acceptance"])


if __name__ == "__main__":
    unittest.main()
