"""Offline acceptance contract for the private Images preview control slice."""

import unittest
from pathlib import Path
import re

import yaml

from scripts.gc_ui_consumer_audit import audit


ROOT = Path(__file__).resolve().parents[2]
STYLES = ROOT / "searx/static/themes/simple/goreecloud-settings-categories.css"
TOKENS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"
RESULTS = ROOT / "searx/templates/simple/results.html"
BROWSER = ROOT / "tests/goreecloud/browser_home_smoke.py"
CONFIG = ROOT / "configs/goreecloud/settings.yml"
GC = 'html[data-gc-consumer="goreecloud-search"]'
OLD = "html[data-glaze-consumer]"


class GCUIImageToolTests(unittest.TestCase):
    def test_preview_control_slice_no_longer_depends_on_retired_selector(self):
        css = STYLES.read_text(encoding="utf-8")
        for suffix in (
            ".goreecloud-image-tools {",
            ".goreecloud-image-tools button {",
            ".goreecloud-image-tools button:disabled {",
            ".goreecloud-image-tools button:focus-visible {",
        ):
            scoped = " body.results_endpoint " + suffix
            self.assertIn(GC + scoped, css)
            self.assertNotIn(OLD + scoped, css)

    def test_supported_touch_and_focus_tokens_and_forced_colors(self):
        css = STYLES.read_text(encoding="utf-8")
        official = TOKENS.read_text(encoding="utf-8")
        for token in (
            "--gc-v1-component-button-height-medium",
            "--gc-v1-component-focus-width",
            "--gc-v1-component-focus-offset",
            "--gc-v1-color-focus-ring",
        ):
            self.assertIn(token + ":", official)
            self.assertIn("var(" + token, css)
        self.assertIn("min-height: var(--gc-v1-component-button-height-medium, 44px)", css)
        self.assertIn("@media (forced-colors: active)", css)
        self.assertIn(GC + " body.results_endpoint .goreecloud-image-tools button:focus-visible {\n    outline-color: Highlight;", css)

    def test_native_user_activation_and_status_feedback_remain_present(self):
        html = RESULTS.read_text(encoding="utf-8")
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn('type="button" id="goreecloud-image-load-all"', html)
        self.assertIn('id="goreecloud-image-load-status" role="status" aria-live="polite"', html)
        self.assertIn("imageLoadTarget:loadAll?.getBoundingClientRect().height ?? 0", browser)
        self.assertIn("geometry['imageLoadButton'] and geometry['imageLoadTarget'] >= 44", browser)

    def test_browser_fixture_renders_conditional_preview_control(self):
        html = RESULTS.read_text(encoding="utf-8")
        browser = BROWSER.read_text(encoding="utf-8")
        settings = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        match = re.search(r"^IMAGE_GALLERY_COUNT = (\d+)\b", browser, re.MULTILINE)
        self.assertIsNotNone(match, "Browser fixture must declare its result count")
        self.assertGreater(int(match.group(1)), 12)
        self.assertIn("for i in range(1, IMAGE_GALLERY_COUNT + 1)", browser)
        self.assertIn("== IMAGE_GALLERY_COUNT", browser)
        self.assertIn("preferences.get_value('image_proxy')", html)
        self.assertIn("results|length > 12", html)
        self.assertTrue(settings["goreecloud"]["private_search"])
        self.assertIs(settings["server"]["image_proxy"], True)
        self.assertIn("image_proxy", settings["preferences"]["lock"])

    def test_measured_debt_decreases_but_strict_gc_ui_acceptance_stays_open(self):
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLessEqual(report["active_legacy_lines"], 402)
        self.assertFalse(report["full_gc_ui_acceptance"])


if __name__ == "__main__":
    unittest.main()
