"""Executable Development quickstart and privacy documentation contracts."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from goreecloud_search.store import search

ROOT = Path(__file__).resolve().parents[1]


class PrivateQuickstartTests(unittest.TestCase):
    def test_readme_uses_private_directory_for_native_and_http_catalog(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('GC_SEARCH_DEMO_DIR="$(mktemp -d /tmp/gc-search-demo.XXXXXXXX)"', readme)
        self.assertIn('--db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3" init', readme)
        self.assertIn('--db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3" serve', readme)
        self.assertIn('goreecloud_search.native --db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3"', readme)
        self.assertNotIn("--db /tmp/gc-search-demo.sqlite3", readme)

    def test_private_quickstart_init_import_and_local_search(self):
        with tempfile.TemporaryDirectory(prefix="gc-private-quickstart-") as directory:
            private = Path(directory)
            self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)
            db = private / "catalog.sqlite3"
            def call(*args):
                return subprocess.run(
                    [sys.executable, "-m", "goreecloud_search", "--db", str(db), *args],
                    cwd=ROOT,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    text=True, capture_output=True, check=False, timeout=12,
                )
            created = call("init")
            self.assertEqual(created.returncode, 0, created.stderr)
            imported = call("import-jsonl", "--input", str(ROOT / "examples/catalog.jsonl"))
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertIn("Imported", imported.stdout)
            self.assertEqual(stat.S_IMODE(db.stat().st_mode), 0o600)
            self.assertTrue(db.is_file())
            self.assertGreaterEqual(len(search(db, "GoreeCloud")), 1)


if __name__ == "__main__":
    unittest.main()
