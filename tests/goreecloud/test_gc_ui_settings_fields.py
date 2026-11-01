"""Offline GC UI contract for private Settings' interactive form controls."""

import unittest
from pathlib import Path

import yaml

from scripts.gc_ui_consumer_audit import audit


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "searx/static/themes/simple/goreecloud-settings-categories.css"
TOKENS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"
PREFERENCES = ROOT / "searx/templates/simple/preferences.html"
LANGUAGE = ROOT / "searx/templates/simple/preferences/language.html"
FOOTER = ROOT / "searx/templates/simple/preferences/footer.html"
BROWSER = ROOT / "tests/goreecloud/browser_home_smoke.py"
CONFIG = ROOT / "configs/goreecloud/settings.yml"
GC = 'html[data-gc-consumer="goreecloud-search"]'
OLD = "html[data-glaze-consumer]"


class GCUISettingsFieldTests(unittest.TestCase):
    def test_real_private_settings_controls_are_present_and_labelled(self):
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        settings = PREFERENCES.read_text(encoding="utf-8")
        language = LANGUAGE.read_text(encoding="utf-8")
        footer = FOOTER.read_text(encoding="utf-8")
        self.assertTrue(config["goreecloud"]["private_search"])
        self.assertIn('class="goreecloud-provider-option"', settings)
        self.assertIn('name="goreecloud_sources"', settings)
        self.assertIn("select name='language' aria-labelledby=", language)
        self.assertNotIn("language", config["preferences"]["lock"])
        self.assertIn('type="submit" class="goreecloud-save-action"', footer)
        self.assertIn("{% if private_query_transport %}", footer)

    def test_settings_field_and_save_controls_use_supported_tokens(self):
        css = CSS.read_text(encoding="utf-8")
        tokens = TOKENS.read_text(encoding="utf-8")
        for token in (
            "--gc-v1-component-field-height",
            "--gc-v1-component-field-radius",
            "--gc-v1-component-button-height-medium",
            "--gc-v1-component-focus-width",
            "--gc-v1-component-focus-offset",
            "--gc-v1-color-focus-ring",
            "--gc-v1-color-primary",
            "--gc-v1-color-on-primary",
        ):
            self.assertIn(token + ":", tokens)
            self.assertIn("var(" + token, css)
        self.assertIn(GC + " body.preferences_endpoint #search_form select,", css)
        self.assertIn(GC + ' body.preferences_endpoint .goreecloud-preferences-actions > input[type="submit"] {', css)
        self.assertNotIn(OLD + " body.preferences_endpoint #search_form select,", css)
        self.assertNotIn(OLD + ' body.preferences_endpoint .goreecloud-preferences-actions > input[type="submit"] {', css)

    def test_keyboard_focus_highlights_the_full_source_option(self):
        css = CSS.read_text(encoding="utf-8")
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn(GC + " body.preferences_endpoint #search_form .goreecloud-provider-option:has(input:focus-visible)", css)
        self.assertIn("sourceLabelHeight: source?.closest('label')?.getBoundingClientRect().height ?? 0", browser)
        self.assertIn("keyboard_source.send_keys(Keys.SPACE)", browser)
        self.assertIn("input.matches(':focus-visible')", browser)
        self.assertIn("source_focus['outline'] == 'solid'", browser)

    def test_forced_colors_and_debt_remain_evidence_bound(self):
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("background: Field; color: FieldText; border-color: FieldText;", css)
        self.assertIn("background: ButtonFace; color: ButtonText; border-color: ButtonText;", css)
        self.assertIn("outline-color: Highlight;", css)
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLessEqual(report["active_legacy_lines"], 366)
        self.assertFalse(report["full_gc_ui_acceptance"])


if __name__ == "__main__":
    unittest.main()
