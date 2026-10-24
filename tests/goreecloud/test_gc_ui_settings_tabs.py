"""Bounded Search Settings tab migration to the supported GC UI consumer contract."""

import unittest
from pathlib import Path

from scripts.gc_ui_consumer_audit import audit


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "searx/static/themes/simple/goreecloud-settings-categories.css"
FOUNDATIONS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"
TEMPLATE = ROOT / "searx/templates/simple/preferences.html"
BROWSER = ROOT / "tests/goreecloud/browser_home_smoke.py"
GC = 'html[data-gc-consumer="goreecloud-search"]'
LEGACY = "html[data-glaze-consumer]"


class GCUISettingsTabsTests(unittest.TestCase):
    def test_tab_rail_and_responsive_styles_use_official_consumer(self):
        css = CSS.read_text(encoding="utf-8")
        for part in (
            "#search_form > .tabs {",
            '#search_form > .tabs > input[type="radio"] {',
            '#search_form > .tabs > label[role="tab"] {',
            '#search_form > .tabs > input[type="radio"]:checked + label {',
            '#search_form > .tabs > input[type="radio"]:focus-visible + label {',
            '#search_form > .tabs > section[role="tabpanel"] {',
        ):
            self.assertIn(GC + " body.preferences_endpoint " + part, css)
            self.assertNotIn(LEGACY + " body.preferences_endpoint " + part, css)

        narrow = css.split("@media (max-width: 360px)", 1)[1]
        self.assertIn(GC + " body.preferences_endpoint #search_form > .tabs > label", narrow)
        self.assertNotIn(LEGACY + " body.preferences_endpoint #search_form > .tabs > label", narrow)

    def test_supported_focus_and_touch_contract(self):
        css = CSS.read_text(encoding="utf-8")
        official = FOUNDATIONS.read_text(encoding="utf-8")
        for token in (
            "--gc-v1-foundation-target-comfortable",
            "--gc-v1-component-focus-width",
            "--gc-v1-color-focus-ring",
        ):
            self.assertIn(token + ":", official)
            self.assertIn("var(" + token, css)
        self.assertIn('input[type="radio"]:focus-visible + label', css)
        self.assertIn("outline-offset: -3px;", css)
        self.assertIn("@media (forced-colors: active)", css)

    def test_native_radio_label_relationship_and_browser_coverage(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn('<input type="radio" name="{{ name }}" id="tab-{{ id }}"', template)
        self.assertIn('<label id="tab-label-{{ id }}" for="tab-{{ id }}"', template)
        self.assertIn('role="tabpanel"', template)
        self.assertIn("tabRelation: label.control === radio", browser)
        self.assertIn("tabHeight: label.getBoundingClientRect().height", browser)
        self.assertIn("driver.find_element(By.ID, 'tab-label-ui').click()", browser)

    def test_migration_reduces_baselined_legacy_debt_without_claiming_completion(self):
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLessEqual(report["active_legacy_lines"], 392)
        self.assertFalse(report["full_gc_ui_acceptance"])


if __name__ == "__main__":
    unittest.main()
