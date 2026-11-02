"""Offline, private SQLite backup/verify/recovery-copy acceptance contracts.

All files are disposable. No network traffic, existing-catalog replacement,
native OS installation or external-provider calls.
"""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from goreecloud_search.recovery import RecoveryError, inspect_catalog, snapshot_catalog
from goreecloud_search.store import import_jsonl, initialize, search


class CatalogRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.index = self.folder / "catalog.sqlite3"
        initialize(self.index)
        self._import("Original Handbook", "private first-party catalog", "original")

    def _import(self, title, description, source):
        data = self.folder / "input.jsonl"
        data.write_text(json.dumps({
            "title": title, "description": description,
            "url": "https://example.org/handbook", "source": source,
        }) + "\n", encoding="utf-8")
        import_jsonl(self.index, data)

    def test_private_round_trip_snapshot_and_integrity(self):
        backup = self.folder / "snapshot.sqlite3"
        self.assertEqual(snapshot_catalog(self.index, backup), 1)
        self.assertEqual(inspect_catalog(backup), 1)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(search(backup, "private")[0]["title"], "Original Handbook")

    def test_restore_copy_never_overwrites_source_or_existing_destination(self):
        backup = self.folder / "snapshot.sqlite3"
        snapshot_catalog(self.index, backup)
        self._import("Later Book", "changed after backup", "recent")
        restored = self.folder / "restored.sqlite3"
        self.assertEqual(snapshot_catalog(backup, restored), 1)
        self.assertEqual(search(restored, "private")[0]["title"], "Original Handbook")
        self.assertEqual(search(self.index, "changed")[0]["title"], "Later Book")
        with self.assertRaisesRegex(RecoveryError, "already exists"):
            snapshot_catalog(backup, restored)
        self.assertEqual(search(restored, "private")[0]["title"], "Original Handbook")

    def test_missing_or_corrupt_or_uninitialized_source_rejected(self):
        with self.assertRaises(RecoveryError):
            inspect_catalog(self.folder / "missing.sqlite3")
        corrupt = self.folder / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a SQLite database")
        with self.assertRaises(RecoveryError):
            snapshot_catalog(corrupt, self.folder / "bad-destination.sqlite3")
        self.assertFalse((self.folder / "bad-destination.sqlite3").exists())
        wrong_schema = self.folder / "wrong-schema.sqlite3"
        with sqlite3.connect(wrong_schema) as db:
            db.execute("CREATE TABLE notes(value TEXT)")
        with self.assertRaises(RecoveryError):
            inspect_catalog(wrong_schema)

    def test_existing_and_dangling_symlink_destination_refused(self):
        target = self.folder / "important.txt"
        target.write_text("do not modify", encoding="utf-8")
        existing = self.folder / "existing.sqlite3"
        existing.write_text("do not overwrite", encoding="utf-8")
        with self.assertRaises(RecoveryError):
            snapshot_catalog(self.index, existing)
        link = self.folder / "link.sqlite3"
        link.symlink_to(target)
        with self.assertRaises(RecoveryError):
            snapshot_catalog(self.index, link)
        dangling = self.folder / "dangling.sqlite3"
        dangling.symlink_to(self.folder / "missing.sqlite3")
        with self.assertRaises(RecoveryError):
            snapshot_catalog(self.index, dangling)
        self.assertEqual(target.read_text(encoding="utf-8"), "do not modify")
        self.assertEqual(existing.read_text(encoding="utf-8"), "do not overwrite")

    def test_symlinked_or_public_destination_directory_refused(self):
        private = self.folder / "private"
        private.mkdir(mode=0o700)
        alias = self.folder / "alias"
        alias.symlink_to(private, target_is_directory=True)
        with self.assertRaises(RecoveryError):
            snapshot_catalog(self.index, alias / "copy.sqlite3")
        self.assertFalse((private / "copy.sqlite3").exists())
        public = self.folder / "public"
        public.mkdir()
        public.chmod(0o755)
        with self.assertRaises(RecoveryError):
            snapshot_catalog(self.index, public / "copy.sqlite3")
        self.assertFalse((public / "copy.sqlite3").exists())

    def test_nested_symlink_destination_ancestry_refused(self):
        owned = self.folder / "owned"
        private = owned / "private"
        private.mkdir(parents=True, mode=0o700)
        alias = self.folder / "alias"
        alias.symlink_to(owned, target_is_directory=True)
        output = alias / "private" / "new-catalog.sqlite3"
        self.assertFalse(output.parent.is_symlink())
        with self.assertRaises(RecoveryError):
            snapshot_catalog(self.index, output)
        self.assertFalse((private / "new-catalog.sqlite3").exists())

    def test_nested_symlink_source_ancestry_refused(self):
        owned = self.folder / "source-owned"
        private = owned / "private"
        private.mkdir(parents=True, mode=0o700)
        source = private / "catalog.sqlite3"
        source.write_bytes(self.index.read_bytes())
        source.chmod(0o600)
        alias = self.folder / "source-alias"
        alias.symlink_to(owned, target_is_directory=True)
        with self.assertRaises(RecoveryError):
            inspect_catalog(alias / "private" / "catalog.sqlite3")
        output = self.folder / "unsafe-source-snapshot.sqlite3"
        with self.assertRaises(RecoveryError):
            snapshot_catalog(alias / "private" / "catalog.sqlite3", output)
        self.assertFalse(output.exists())

    def test_source_file_must_be_owner_private_and_not_symlink(self):
        public = self.folder / "public-index.sqlite3"
        public.write_bytes(self.index.read_bytes())
        public.chmod(0o644)
        with self.assertRaises(RecoveryError):
            inspect_catalog(public)
        alias = self.folder / "index-link.sqlite3"
        alias.symlink_to(self.index)
        with self.assertRaises(RecoveryError):
            inspect_catalog(alias)

    def test_reject_relative_destinations_and_sources(self):
        with self.assertRaises(RecoveryError):
            snapshot_catalog(self.index, Path("relative.sqlite3"))
        with self.assertRaises(RecoveryError):
            inspect_catalog(Path("relative.sqlite3"))
        self.assertEqual(inspect_catalog(self.index), 1)

    def test_online_snapshot_includes_committed_wal_rows(self):
        # The SQLite backup API must work for a source in WAL mode.
        with sqlite3.connect(self.index) as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute(
                "INSERT INTO documents (title, description, url, source)"
                " VALUES (?, ?, ?, ?)",
                ("WAL Committed", "snapshot consistency", "https://example.org/wal", "local"),
            )
        backup = self.folder / "wal-backup.sqlite3"
        self.assertEqual(snapshot_catalog(self.index, backup), 2)
        self.assertEqual(len(search(backup, "snapshot")), 1)

    def test_cli_backup_verify_and_restore_copy_in_fresh_paths(self):
        backup = self.folder / "cli-snapshot.sqlite3"
        restored = self.folder / "cli-restored.sqlite3"
        command = [sys.executable, "-m", "goreecloud_search"]
        workdir = Path(__file__).resolve().parents[1]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

        def run(*args):
            return subprocess.run(command + list(args), cwd=workdir, env=env,
                                  text=True, capture_output=True, timeout=12, check=False)

        created = run("--db", str(self.index), "backup", "--output", str(backup))
        self.assertEqual(created.returncode, 0, created.stderr)
        verified = run("verify-backup", "--input", str(backup))
        self.assertEqual(verified.returncode, 0, verified.stderr)
        restored_result = run("restore-copy", "--input", str(backup), "--output", str(restored))
        self.assertEqual(restored_result.returncode, 0, restored_result.stderr)
        self.assertEqual(inspect_catalog(restored), 1)
        attempted = run("restore-copy", "--input", str(backup), "--output", str(restored))
        self.assertNotEqual(attempted.returncode, 0)
        self.assertEqual(inspect_catalog(restored), 1)


if __name__ == "__main__":
    unittest.main()
