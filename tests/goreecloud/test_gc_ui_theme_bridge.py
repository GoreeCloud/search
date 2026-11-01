"""Search's first controlled GC UI semantic runtime migration slice."""

import shutil
import subprocess
import unittest
from pathlib import Path

from scripts.gc_ui_consumer_audit import audit


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "searx/templates/simple/base.html"
CSS = ROOT / "searx/static/themes/simple/goreecloud-mockup.css"
THEME = ROOT / "searx/static/themes/simple/goreecloud-theme.js"
FOUNDATIONS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"


class GCUIThemeBridgeTests(unittest.TestCase):
    def test_root_exposes_new_consumer_contract_while_preserving_transition(self):
        html = BASE.read_text(encoding="utf-8")
        self.assertIn('data-glaze-consumer="goreecloud-search" data-gc-consumer="goreecloud-search"', html)
        self.assertIn('data-gc-mode="dark"', html)
        self.assertIn('data-gc-mode="light"', html)
        self.assertIn("preferences.get_value('simple_style') in ('dark', 'black')", html)
        self.assertIn("preferences.get_value('simple_style') == 'light'", html)
        self.assertIn("goreecloud-theme.js", html)

    def test_migrated_real_controls_consume_official_semantics(self):
        css = CSS.read_text(encoding="utf-8")
        official = FOUNDATIONS.read_text(encoding="utf-8")
        for token in (
            "--gc-v1-component-button-height-medium",
            "--gc-v1-component-focus-width",
            "--gc-v1-component-focus-offset",
            "--gc-v1-foundation-radius-pill",
            "--gc-v1-color-focus-ring",
        ):
            self.assertIn(token + ":", official, token)
            self.assertIn("var(" + token, css, token)
        self.assertRegex(css, r'html\[data-gc-consumer="goreecloud-search"\] \.goreecloud-theme-toggle:focus-visible')
        self.assertRegex(css, r'html\.no-js\[data-gc-consumer="goreecloud-search"\] \.goreecloud-theme-toggle \{ display: none; \}')
        self.assertRegex(css, r'@media \(forced-colors: active\) \{[\s\S]*?\.goreecloud-theme-toggle:focus-visible \{ outline-color: Highlight; \}')
        self.assertIn('html[data-gc-consumer="goreecloud-search"] .goreecloud-skip-link', css)
        self.assertNotRegex(css, r'html\[data-glaze-consumer\] \.goreecloud-theme-toggle')
        self.assertNotRegex(css, r'html\[data-glaze-consumer\] \.goreecloud-skip-link')

    def test_theme_controller_sets_the_exact_foundations_mode(self):
        source = THEME.read_text(encoding="utf-8")
        self.assertIn("html.setAttribute('data-gc-mode', active ? 'dark' : 'light')", source)
        self.assertIn("window.matchMedia('(prefers-color-scheme: dark)')", source)
        self.assertIn("button.setAttribute('aria-pressed', String(active))", source)

    def test_migration_is_a_measured_legacy_decrease_not_a_claim_of_acceptance(self):
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLessEqual(report["active_legacy_lines"], 430)
        self.assertLessEqual(report["vendor_legacy_css_files"], 66)
        self.assertFalse(report["full_gc_ui_acceptance"])

    @unittest.skipUnless(shutil.which("node"), "Node unavailable for offline JS DOM contract")
    def test_actual_javascript_runtime_without_network_or_browser(self):
        run = subprocess.run(
            ["node", "tests/goreecloud/gc_ui_theme_contract.cjs"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("PASS GC UI Search theme bridge", run.stdout)


if __name__ == "__main__":
    unittest.main()
