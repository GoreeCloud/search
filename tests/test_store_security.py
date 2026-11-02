"""Offline active-catalog path, ownership and filesystem guard contracts."""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from goreecloud_search.store import connect, import_jsonl, initialize, search


class ActiveCatalogSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.db = self.root / "local.sqlite3"
        initialize(self.db)

    def test_indirect_symlinked_index_directory_refused_on_read_and_init(self):
        private = self.root / "private"
        nested = private / "nested"
        nested.mkdir(parents=True, mode=0o700)
        actual = nested / "safe.sqlite3"
        initialize(actual)
        alias = self.root / "alias"
        alias.symlink_to(private, target_is_directory=True)
        indirect = alias / "nested" / "safe.sqlite3"
        self.assertFalse(indirect.parent.is_symlink())
        with self.assertRaises(PermissionError):
            search(indirect, "local")
        with self.assertRaises(PermissionError):
            initialize(indirect)
        with self.assertRaises(PermissionError):
            initialize(alias / "nested" / "new.sqlite3")
        self.assertFalse((nested / "new.sqlite3").exists())

    def test_existing_public_index_directory_refused_for_init_and_search(self):
        parent = self.root / "public"
        parent.mkdir()
        parent.chmod(0o755)
        output = parent / "index.sqlite3"
        with self.assertRaises(PermissionError):
            initialize(output)
        self.assertFalse(output.exists())
        parent.chmod(0o700)
        initialize(output)
        parent.chmod(0o755)
        with self.assertRaises(PermissionError):
            search(output, "local")
        self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o755)

    def test_owner_mismatch_fails_without_changing_existing_file(self):
        old_mode = stat.S_IMODE(self.db.stat().st_mode)
        with patch("goreecloud_search.store.os.getuid", return_value=os.getuid() + 1):
            with self.assertRaises(PermissionError):
                search(self.db, "nothing")
            with self.assertRaises(PermissionError):
                initialize(self.db)
        self.assertEqual(stat.S_IMODE(self.db.stat().st_mode), old_mode)
        self.assertEqual(search(self.db, "nothing"), [])

    def test_relative_and_parent_traversal_paths_are_refused(self):
        candidate = self.root / "subdir" / ".." / "local.sqlite3"
        for unsafe in (Path("relative.sqlite3"), candidate):
            with self.subTest(path=str(unsafe)):
                with self.assertRaises(PermissionError):
                    initialize(unsafe)
                with self.assertRaises(PermissionError):
                    search(unsafe, "hello")
        self.assertEqual(search(self.db, "nothing"), [])

    def test_directory_and_symlink_can_never_act_as_index(self):
        folder = self.root / "folder.sqlite3"
        folder.mkdir(mode=0o700)
        for operation in (initialize, lambda p: search(p, "hello")):
            with self.assertRaises(PermissionError):
                operation(folder)
        link = self.root / "indirect.sqlite3"
        link.symlink_to(self.db)
        with self.assertRaises(PermissionError):
            initialize(link)
        with self.assertRaises(PermissionError):
            search(link, "hello")
        self.assertTrue(self.db.is_file())

    def test_uri_special_filename_roundtrip_and_private_file(self):
        special = self.root / "curated #? % index.sqlite3"
        initialize(special)
        data = self.root / "fixture.jsonl"
        data.write_text(json.dumps({
            "title": "GoreeCloud Original",
            "description": "Safe private SQLite catalog",
            "url": "https://example.org/catalog",
            "source": "local",
        }) + "\n", encoding="utf-8")
        self.assertEqual(import_jsonl(special, data), 1)
        self.assertEqual(search(special, "original")[0]["title"], "GoreeCloud Original")
        self.assertEqual(stat.S_IMODE(special.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
