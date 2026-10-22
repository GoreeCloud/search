import json
import tempfile
import unittest
from pathlib import Path

from scripts.gc_ui_consumer_audit import assess, audit, inventory


REPO = Path(__file__).resolve().parents[2]


class GCUIConsumerAuditTests(unittest.TestCase):
    def test_real_consumer_inventory_is_at_or_below_frozen_legacy_budget(self):
        report = audit(REPO, REPO / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertFalse(report["full_gc_ui_acceptance"])
        self.assertGreater(report["active_legacy_lines"], 0)

    def test_strict_mode_remains_open_until_actual_migration(self):
        report = audit(REPO, REPO / "docs/goreecloud/gc-ui-legacy-baseline.json", strict=True)
        self.assertFalse(report["passed"])
        self.assertIn("searx/templates/simple/base.html", report["active_files"])

    def test_detects_new_file_and_increased_legacy_use(self):
        observed = {"old.css": 3, "new.css": 1}
        passed, problems = assess(observed, {"old.css": 2})
        self.assertFalse(passed)
        self.assertEqual(problems["old.css"], {"observed": 3, "maximum": 2})
        self.assertEqual(problems["new.css"], {"observed": 1, "maximum": 0})

    def test_migration_reduces_baseline_without_edits_to_allowance(self):
        self.assertEqual(assess({"old.css": 1}, {"old.css": 5}), (True, {}))
        self.assertEqual(assess({}, {"old.css": 5}, strict=True), (True, {}))

    def test_scans_first_party_ui_but_not_bundled_historical_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "searx/templates/simple/base.html"
            template.parent.mkdir(parents=True)
            template.write_text('<main data-glaze-semantic-surface="protected">\nplain text\n', encoding="utf-8")
            css = root / "searx/static/themes/simple/goreecloud.css"
            css.parent.mkdir(parents=True)
            css.write_text('a { color: var(--glz141-semantic-foreground); }\n', encoding="utf-8")
            vendor = root / "searx/static/themes/simple/glaze/css/glaze.css"
            vendor.parent.mkdir(parents=True)
            vendor.write_text("glaze\n", encoding="utf-8")
            self.assertEqual(inventory(root), {
                "searx/static/themes/simple/goreecloud.css": 1,
                "searx/templates/simple/base.html": 1,
            })
            baseline = root / "baseline.json"
            baseline.write_text(json.dumps({"maximum_active_legacy_lines": {
                "searx/templates/simple/base.html": 1
            }}), encoding="utf-8")
            report = audit(root, baseline)
            self.assertFalse(report["passed"])
            self.assertEqual(report["vendor_legacy_css_files"], 1)


if __name__ == "__main__":
    unittest.main()
