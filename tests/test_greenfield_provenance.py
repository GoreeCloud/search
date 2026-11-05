"""Clean-slate Search source gate; synthetic fixtures contain no retired code."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.verify_greenfield import legacy_source_violations


ROOT = Path(__file__).resolve().parents[1]


class GreenfieldProvenanceTests(unittest.TestCase):
    def fixture(self, directory: str) -> Path:
        root = Path(directory)
        (root / "goreecloud_search").mkdir()
        (root / "goreecloud_search" / "original.py").write_text(
            "import json\nfrom urllib.parse import urlsplit\n"
            "# A comment about SearXNG HTTP integration is allowed.\n",
            encoding="utf-8",
        )
        return root

    def test_current_first_party_tree_contains_no_retired_source(self):
        self.assertEqual(legacy_source_violations(ROOT), [])

    def test_docs_and_optional_http_provider_mentions_are_not_banned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            (root / "docs").mkdir()
            (root / "docs" / "HISTORICAL_SEARCH.md").write_text(
                "The old searx/engine tree is intentionally not used.\n",
                encoding="utf-8",
            )
            (root / "goreecloud_search" / "original.py").write_text(
                'SEARXNG_PROVIDER = "http://127.0.0.1:8888/search"\n',
                encoding="utf-8",
            )
            self.assertEqual(legacy_source_violations(root), [])

    def test_rejected_root_names_include_case_variants(self):
        for name in ("searx", "SEARXNG", "legacy-search", "Recovered-Search"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = self.fixture(directory)
                (root / name).mkdir()
                self.assertTrue(legacy_source_violations(root))

    def test_direct_imports_are_rejected_without_executing_source(self):
        for code in (
            "import searx.engines\n",
            "import json, searxng.old\n",
            "from searx.engines import old_engine\n",
            "from searxng import app\n",
        ):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                root = self.fixture(directory)
                (root / "goreecloud_search" / "original.py").write_text(
                    code, encoding="utf-8"
                )
                self.assertTrue(any("Retired package import" in x
                                    for x in legacy_source_violations(root)))

    def test_invalid_or_symlinked_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            original = root / "goreecloud_search" / "original.py"
            original.write_text("def invalid(:\n", encoding="utf-8")
            self.assertTrue(any("invalid Search source" in x
                                for x in legacy_source_violations(root)))
            original.unlink()
            original.symlink_to(root / "docs" / "nonexistent.py")
            self.assertTrue(any("Symlinked Search source" in x
                                for x in legacy_source_violations(root)))


if __name__ == "__main__":
    unittest.main()
