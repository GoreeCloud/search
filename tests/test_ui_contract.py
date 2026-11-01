"""Static, offline UI integration guard; not a substitute for browser/a11y testing."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UIContractTests(unittest.TestCase):
    def test_explicit_source_and_consent_controls(self):
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        for fragment in ('id="source-select"', 'id="share-query"',
                         'value="local"', 'value="brave" disabled',
                         'value="searxng" disabled', 'aria-describedby="provider-notice"'):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, html)

    def test_privacy_disclosure_names_provider_egress(self):
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertIn("Brave sends the query", html)
        self.assertIn("may contact external search engines", html)
        self.assertIn("No external connection is made unless", html)

    def test_client_uses_safe_text_rendering_and_clears_consent(self):
        js = (ROOT / "web/app.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", js)
        self.assertIn("link.textContent = entry.title", js)
        self.assertIn('link.rel = "noopener noreferrer"', js)
        self.assertIn("shareQuery.checked = false", js)
        self.assertIn("sourceSelect.value = \"local\"", js)
        self.assertIn("share_query:", js)

    def test_accessible_status_announces_totals_and_activity(self):
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/app.js").read_text(encoding="utf-8")
        self.assertIn('aria-live="polite" aria-atomic="true"', html)
        self.assertIn('aria-busy="false"', html)
        self.assertIn('aria-controls="result-list"', html)
        self.assertIn('resultList.setAttribute("aria-busy", "true")', js)
        self.assertIn('resultList.setAttribute("aria-busy", "false")', js)
        self.assertIn('result found.', js)
        self.assertIn('results found.', js)
        self.assertNotIn('data.count ? ""', js)

    def test_malformed_result_cannot_break_sibling_rendering(self):
        js = (ROOT / "web/app.js").read_text(encoding="utf-8")
        self.assertIn('try {\n    url = new URL(entry.url);', js)
        self.assertIn('if (!entry || typeof entry !== "object") return false;', js)
        self.assertIn('if (!Array.isArray(data.results))', js)
        self.assertIn('data.results.reduce(', js)
        self.assertIn('link.textContent = entry.title', js)
        self.assertNotIn('innerHTML', js)

    def test_ui_uses_semantic_design_tokens_and_no_remote_script(self):
        css = (ROOT / "web/styles.css").read_text(encoding="utf-8")
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertIn(".provider-fields", css)
        self.assertIn("var(--gc-brand)", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn('src="/app.js"', html)
        self.assertNotIn('src="https://', html)


if __name__ == "__main__":
    unittest.main()
