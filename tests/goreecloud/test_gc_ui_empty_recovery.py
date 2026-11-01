"""Offline GC UI contract for the real no-results and retry experience."""

import unittest
from pathlib import Path

from scripts.gc_ui_consumer_audit import audit


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "searx/static/themes/simple/goreecloud-search.css"
TOKENS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"
NO_RESULTS = ROOT / "searx/templates/simple/messages/no_results.html"
BROWSER = ROOT / "tests/goreecloud/browser_home_smoke.py"
GC = 'html[data-gc-consumer="goreecloud-search"]'
OLD = "html[data-glaze-consumer]"


class GCUIEmptyRecoveryTests(unittest.TestCase):
    def test_actual_failure_offers_no_fallback_and_native_post(self):
        html = NO_RESULTS.read_text(encoding="utf-8")
        self.assertIn('role="status" aria-labelledby="goreecloud-no-results-title"', html)
        self.assertIn('class="goreecloud-empty-retry" method="post" action="{{ url_for(\'search\') }}"', html)
        self.assertIn('name="engines" value="{{ selected_engine_post }}"', html)
        self.assertIn('name="q" value="{{ source_switch_query }}"', html)
        self.assertIn('type="submit">Retry selected sources</button>', html)
        self.assertIn("{% if goreecloud_retry_blocked %}", html)
        self.assertIn("No automatic provider substitution occurred.", html)

    def test_foundations_tokenized_surface_and_focus_replace_legacy_selector(self):
        css = CSS.read_text(encoding="utf-8")
        tokens = TOKENS.read_text(encoding="utf-8")
        for token in (
            "--gc-v1-color-surface",
            "--gc-v1-color-on-surface",
            "--gc-v1-color-on-surface-muted",
            "--gc-v1-color-primary",
            "--gc-v1-color-on-primary",
            "--gc-v1-color-focus-ring",
            "--gc-v1-component-button-height-medium",
            "--gc-v1-component-focus-width",
            "--gc-v1-component-focus-offset",
        ):
            self.assertIn(token + ":", tokens)
            self.assertIn("var(" + token, css)
        for selector in (
            ".goreecloud-empty-state",
            ".goreecloud-empty-state h2",
            ".goreecloud-empty-state p",
            ".goreecloud-empty-retry",
            ".goreecloud-empty-retry button",
            ".goreecloud-empty-retry button:focus-visible",
        ):
            self.assertIn(GC + " " + selector, css, selector)
            self.assertNotIn(OLD + " " + selector, css, selector)

    def test_keyboard_mobile_forced_colors_and_private_post_in_browser_contract(self):
        css = CSS.read_text(encoding="utf-8")
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn('outline-color: Highlight;', css)
        self.assertIn('background: ButtonFace; color: ButtonText; border-color: ButtonText;', css)
        self.assertIn("retry.send_keys(Keys.SPACE)", browser)
        self.assertIn("retry.matches(':focus-visible')", browser)
        self.assertIn("retry_focus['visible'] and retry_focus['focused']", browser)
        self.assertIn("retry_focus['height'] >= 44", browser)
        self.assertIn("retry_focus['method'] == 'post'", browser)
        self.assertIn("assert not driver.execute_script('return location.search')", browser)

    def test_migration_debt_improves_without_claiming_full_acceptance(self):
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLessEqual(report["active_legacy_lines"], 356)
        self.assertFalse(report["full_gc_ui_acceptance"])


if __name__ == "__main__":
    unittest.main()
