"""Bounded SQLite lock and rollback recovery using a disposable Development database.

This test never opens configured Search databases or performs provider requests.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from searx.sqlitedb import SQLiteAppl


class LockRecoveryProbe(SQLiteAppl):
    DB_SCHEMA = 1
    DDL_CREATE_TABLES = {
        "lock_events": (
            "CREATE TABLE IF NOT EXISTS lock_events "
            "(writer INTEGER NOT NULL, value INTEGER NOT NULL, "
            "PRIMARY KEY (writer, value))"
        ),
    }


class SearchSQLiteLockRecoveryTests(unittest.TestCase):
    def test_locked_writer_rolls_back_and_retry_commits(self):
        with tempfile.TemporaryDirectory(prefix="gc-search-lock-test-") as directory:
            app = LockRecoveryProbe(str(Path(directory) / "lock.sqlite3"))
            self.assertEqual("wal", app.DB.execute("PRAGMA journal_mode").fetchone()[0].lower())
            lock_owner = sqlite3.connect(app.db_url, timeout=1, isolation_level=None)
            retrying_writer = sqlite3.connect(app.db_url, timeout=0.2, isolation_level=None)
            try:
                lock_owner.execute("BEGIN IMMEDIATE")
                lock_owner.execute(
                    "INSERT INTO lock_events(writer, value) VALUES (1, 1)"
                )
                with self.assertRaises(sqlite3.OperationalError) as caught:
                    retrying_writer.execute(
                        "INSERT INTO lock_events(writer, value) VALUES (2, 1)"
                    )
                self.assertIn("locked", str(caught.exception).lower())
                lock_owner.execute("ROLLBACK")
                self.assertEqual(
                    0, app.DB.execute("SELECT COUNT(*) FROM lock_events").fetchone()[0]
                )
                retrying_writer.execute(
                    "INSERT INTO lock_events(writer, value) VALUES (2, 1)"
                )
                self.assertEqual(
                    [(2, 1)],
                    app.DB.execute(
                        "SELECT writer, value FROM lock_events ORDER BY writer, value"
                    ).fetchall(),
                )
                self.assertEqual(
                    "ok", app.DB.execute("PRAGMA quick_check").fetchone()[0]
                )
            finally:
                if lock_owner.in_transaction:
                    lock_owner.rollback()
                retrying_writer.close()
                lock_owner.close()


if __name__ == "__main__":
    unittest.main()
