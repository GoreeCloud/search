# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthetic, no-network, never-overwrite Search index backup/restore evidence."""

from contextlib import redirect_stdout, redirect_stderr
import hashlib
from io import StringIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from native_search.index import SearchIndex
from scripts.native_index_recovery_probe import RecoveryBlocked, exercise, main


class NativeIndexRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.db"
        self.backup = self.root / "new-backup.db"
        self.restored = self.root / "new-probe.db"
        with SearchIndex(self.source) as index:
            index.add(url="https://example.org/a", title="Approved First Document",
                      body="A controlled recovery index fixture for GoreeCloud search")
            index.add(url="https://example.org/b", title="Approved Second Document",
                      body="The recovery exercise must retain both FTS records")

    def test_roundtrip_restores_search_and_preserves_source_bytes(self):
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        evidence = exercise(self.source, self.backup, self.restored)
        self.assertEqual("goreecloud.search.native-index-recovery-probe.v1", evidence["schema"])
        self.assertEqual(2, evidence["document_count"])
        self.assertEqual(before, hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(hashlib.sha256(self.backup.read_bytes()).hexdigest(),
                         evidence["backup_sha256"])
        self.assertIn("everkeep_platform_integration", evidence["not_evaluated"])
        with SearchIndex(self.restored) as index:
            self.assertEqual(2, index.count())
            self.assertEqual(["https://example.org/a"],
                             [row.url for row in index.search("controlled")])
            self.assertEqual(["https://example.org/b"],
                             [row.url for row in index.search("exercise")])

    def test_never_overwrites_existing_backup_or_probe(self):
        self.backup.write_bytes(b"important original backup")
        with self.assertRaisesRegex(RecoveryBlocked, "never be overwritten"):
            exercise(self.source, self.backup, self.restored)
        self.assertEqual(b"important original backup", self.backup.read_bytes())
        self.assertFalse(self.restored.exists())
        self.backup.unlink()
        self.restored.write_bytes(b"important recovery work")
        with self.assertRaisesRegex(RecoveryBlocked, "never be overwritten"):
            exercise(self.source, self.backup, self.restored)
        self.assertEqual(b"important recovery work", self.restored.read_bytes())
        self.assertFalse(self.backup.exists())

    def test_source_and_destination_symlinks_are_refused(self):
        alias = self.root / "alias.db"
        alias.symlink_to(self.source)
        with self.assertRaisesRegex(RecoveryBlocked, "symlink"):
            exercise(alias, self.backup, self.restored)
        self.backup.symlink_to(self.source)
        with self.assertRaisesRegex(RecoveryBlocked, "symlink"):
            exercise(self.source, self.backup, self.restored)
        self.assertFalse(self.restored.exists())

    def test_non_sqlite_or_other_schema_is_refused_and_no_outputs_remain(self):
        self.source.write_bytes(b"not a database")
        with self.assertRaisesRegex(RecoveryBlocked, "regular SQLite"):
            exercise(self.source, self.backup, self.restored)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.restored.exists())
        self.source.unlink()
        with sqlite3.connect(self.source) as db:
            db.execute("CREATE TABLE unrelated (key TEXT)")
        with self.assertRaisesRegex(RecoveryBlocked, "complete owned Search index"):
            exercise(self.source, self.backup, self.restored)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.restored.exists())

    def test_plain_table_cannot_impersonate_the_fts5_virtual_index(self):
        self.source.unlink()
        with sqlite3.connect(self.source) as db:
            db.execute("CREATE TABLE pages (id INTEGER PRIMARY KEY)")
            db.execute("CREATE TABLE pages_fts (pages_fts TEXT)")
            for event, suffix in (("INSERT", "ai"), ("DELETE", "ad"), ("UPDATE", "au")):
                db.execute(f"CREATE TRIGGER pages_{suffix} AFTER {event} ON pages BEGIN "
                           "SELECT 1; END")
        with self.assertRaisesRegex(RecoveryBlocked, "actual FTS5 virtual table"):
            exercise(self.source, self.backup, self.restored)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.restored.exists())

    def test_repeated_snapshot_captures_new_revision_without_changing_old(self):
        first = exercise(self.source, self.backup, self.restored)
        with SearchIndex(self.source) as index:
            index.add(url="https://example.org/c", title="Later Revision",
                      body="This document must not appear in the first backup")
        second = exercise(self.source, self.root / "backup2.db", self.root / "probe2.db")
        self.assertEqual(2, first["document_count"])
        self.assertEqual(3, second["document_count"])
        with SearchIndex(self.restored) as old:
            self.assertEqual(0, len(old.search("later")))

    def test_cli_omits_urls_queries_content_and_local_paths(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(0, main(["--source", str(self.source), "--backup", str(self.backup),
                                      "--restore-probe", str(self.restored)]))
        decoded = json.loads(output.getvalue())
        self.assertEqual(2, decoded["document_count"])
        self.assertNotIn(str(self.source), output.getvalue())
        self.assertNotIn("example.org", output.getvalue())
        self.assertNotIn("GoreeCloud search", output.getvalue())
        err = StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as blocked:
            main(["--source", str(self.source), "--backup", str(self.backup),
                  "--restore-probe", str(self.restored)])
        self.assertEqual(2, blocked.exception.code)
        self.assertIn("NATIVE_INDEX_RECOVERY_BLOCKED", err.getvalue())


if __name__ == "__main__":
    unittest.main()
