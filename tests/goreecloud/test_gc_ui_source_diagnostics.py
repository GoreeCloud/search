"""Offline GC UI contract for private result-source diagnostics and retry."""

import unittest
from pathlib import Path

from scripts.gc_ui_consumer_audit import audit


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "searx/static/themes/simple/goreecloud-results.css"
TOKENS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"
DIAGNOSTICS = ROOT / "searx/templates/simple/goreecloud_source_diagnostics.html"
BROWSER = ROOT / "tests/goreecloud/browser_home_smoke.py"
GC = 'html[data-gc-consumer="goreecloud-search"]'
OLD = "html[data-glaze-consumer]"


class GCUISourceDiagnosticTests(unittest.TestCase):
    def test_actual_partial_response_renders_disclosure_and_native_post(self):
        html = DIAGNOSTICS.read_text(encoding="utf-8")
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn("{% if private_query_transport %}", html)
        self.assertIn('class="goreecloud-source-diagnostics"', html)
        self.assertIn("unresponsive_engines and (results or answers)", html)
        self.assertIn('method="post" action="{{ url_for(\'search\') }}"', html)
        self.assertIn('class="goreecloud-empty-retry goreecloud-partial-retry"', html)
        self.assertIn('<button type="submit">Retry same sources</button>', html)
        self.assertIn("class SyntheticBrowserPartialSearch", browser)
        self.assertIn("response.get_ordered_results = lambda: [result]", browser)
        self.assertIn("response.unresponsive_engines = [", browser)

    def test_disclosure_and_retry_use_supported_targets_focus_and_color(self):
        css = CSS.read_text(encoding="utf-8")
        tokens = TOKENS.read_text(encoding="utf-8")
        for token in (
            "--gc-v1-foundation-target-comfortable",
            "--gc-v1-component-button-height-medium",
            "--gc-v1-component-focus-width",
            "--gc-v1-component-focus-offset",
            "--gc-v1-color-focus-ring",
            "--gc-v1-color-primary",
            "--gc-v1-color-on-primary",
        ):
            self.assertIn(token + ":", tokens)
            self.assertIn("var(" + token, css)
        self.assertIn(GC + " body.results_endpoint .goreecloud-source-diagnostics > summary {", css)
        self.assertIn(GC + " body.results_endpoint .goreecloud-source-diagnostics > summary:focus-visible {", css)
        self.assertIn(GC + " body.results_endpoint .goreecloud-source-diagnostics .goreecloud-empty-retry button {", css)
        self.assertNotIn(OLD + " body.results_endpoint .goreecloud-source-diagnostics summary {", css)
        self.assertNotIn(OLD + " body.results_endpoint .goreecloud-source-diagnostics .goreecloud-empty-retry button {", css)
        self.assertIn("display: list-item;", css)

    def test_browser_contract_exercises_keyboard_and_responsive_actual_controls(self):
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn("summary.send_keys(Keys.SPACE)", browser)
        self.assertIn("summary.matches(':focus-visible')", browser)
        self.assertIn("summary_focus['expanded'] and summary_focus['focused']", browser)
        self.assertIn("summaryHeight:summary.getBoundingClientRect().height", browser)
        self.assertIn("buttonHeight:retry.getBoundingClientRect().height", browser)
        self.assertIn("retry.type==='submit' && retry.form?.method==='post'", browser)
        self.assertIn("(320, 760, 'phone-small')", browser)

    def test_forced_colors_and_strict_acceptance_remain_open(self):
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("outline-color: Highlight;", css)
        self.assertIn("background: ButtonFace; color: ButtonText; border-color: ButtonText;", css)
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLessEqual(report["active_legacy_lines"], 364)
        self.assertFalse(report["full_gc_ui_acceptance"])


if __name__ == "__main__":
    unittest.main()
