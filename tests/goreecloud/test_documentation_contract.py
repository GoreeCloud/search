"""Prevent stale source-allowlist claims in user-facing Development docs."""

import unittest
from pathlib import Path

from searx.goreecloud_policy import BUILTIN_SEARCH_SOURCES, SEARCH_SOURCE_FAMILIES


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CURRENT_CONTRACT_DOCS = (
    "README.md",
    "docs/goreecloud/LOCAL-JSON-API.md",
    "docs/goreecloud/ROADMAP.md",
    "docs/goreecloud/SECURITY-BOUNDARIES.md",
)


class DocumentationContractTests(unittest.TestCase):

    def test_three_family_allowlist_is_documented_in_current_contracts(self):
        self.assertEqual(
            {"brave", "startpage", "qwant", "duckduckgo", "ecosia", "bing", "google"},
            set(SEARCH_SOURCE_FAMILIES["general"]),
        )
        self.assertEqual(24, len(BUILTIN_SEARCH_SOURCES))
        for relative_path in CURRENT_CONTRACT_DOCS:
            with self.subTest(document=relative_path):
                text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8").lower()
                for provider in ("brave", "startpage", "qwant", "duckduckgo", "ecosia", "bing", "google"):
                    self.assertIn(provider, text)
                self.assertNotIn("exactly two permitted", text)
                self.assertNotIn("exactly two built-in", text)
                self.assertNotIn("two-provider selected-source", text)

    def test_video_selection_never_implies_startpage_fallback(self):
        self.assertEqual(
            {"brave", "qwant", "duckduckgo", "bing", "google"},
            set(SEARCH_SOURCE_FAMILIES["videos"]),
        )
        self.assertNotIn("startpage", SEARCH_SOURCE_FAMILIES["videos"])


if __name__ == "__main__":
    unittest.main()
