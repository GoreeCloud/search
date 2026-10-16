"""Development-only interrupted-writer and locked-database recovery checks.

Uses only disposable SQLite databases under TemporaryDirectory. Never opens
Search's configured cache, production data, provider engines or credentials.
"""
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from searx.sqlitedb import SQLiteAppl


class RecoveryProbe(SQLiteAppl):
    DB_SCHEMA = 1
    DDL_CREATE_TABLES = {
        "recovery_events": (
            "CREATE TABLE IF NOT EXISTS recovery_events "
            "(worker INTEGER NOT NULL, sequence INTEGER NOT NULL, "
            "PRIMARY KEY (worker, sequence))"
        )
    }


class SQLiteRecoveryQualification(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gc-search-recovery-")
        self.addCleanup(temporary.cleanup)
        self.db_url = str(Path(temporary.name) / "recovery.sqlite3")
        self.app = RecoveryProbe(self.db_url)
        self.assertEqual("wal", self.app.DB.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0].lower())

    def test_locked_writer_times_out_then_recovers_without_partial_write(self):
        lock_owner = sqlite3.connect(self.db_url, isolation_level=None, timeout=1)
        blocked_writer = sqlite3.connect(self.db_url, isolation_level=None, timeout=.2)
        try:
            lock_owner.execute("BEGIN IMMEDIATE")
            lock_owner.execute(
                "INSERT INTO recovery_events(worker, sequence) VALUES (1, 1)"
            )
            with self.assertRaises(sqlite3.OperationalError) as caught:
                blocked_writer.execute(
                    "INSERT INTO recovery_events(worker, sequence) VALUES (2, 1)"
                )
            self.assertIn("locked", str(caught.exception).lower())
            lock_owner.execute("ROLLBACK")
            self.assertEqual(
                0, self.app.DB.execute("SELECT COUNT(*) FROM recovery_events").fetchone()[0]
            )
            blocked_writer.execute(
                "INSERT INTO recovery_events(worker, sequence) VALUES (2, 1)"
            )
            self.assertEqual(
                [(2, 1)],
                self.app.DB.execute(
                    "SELECT worker, sequence FROM recovery_events ORDER BY worker"
                ).fetchall()
            )
            self.assertEqual(
                "ok", self.app.DB.execute("PRAGMA quick_check").fetchone()[0]
            )
        finally:
            if lock_owner.in_transaction:
                lock_owner.rollback()
            blocked_writer.close()
            lock_owner.close()

    def test_abrupt_writer_exit_keeps_committed_rows_and_discards_uncommitted(self):
        child_code = (
            "import sqlite3,sys,time\n"
            "conn=sqlite3.connect(sys.argv[1], timeout=2)\n"
            "conn.execute('PRAGMA journal_mode=WAL')\n"
            "conn.execute('INSERT INTO recovery_events(worker,sequence) VALUES (3,1)')\n"
            "conn.commit()\n"
            "conn.execute('BEGIN IMMEDIATE')\n"
            "conn.execute('INSERT INTO recovery_events(worker,sequence) VALUES (3,2)')\n"
            "print('READY', flush=True)\n"
            "time.sleep(60)\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", child_code, self.db_url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertIsNotNone(process.stdout)
            readable, _, _ = select.select([process.stdout], [], [], 10)
            self.assertTrue(readable, "Child writer failed to reach the ready state")
            self.assertEqual("READY", process.stdout.readline().strip())
            self.assertIsNone(process.poll(), "Writer exited before simulated interruption")
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)

        reopened = RecoveryProbe(self.db_url)
        connection = reopened.DB
        self.assertEqual(
            [(3, 1)],
            connection.execute(
                "SELECT worker, sequence FROM recovery_events ORDER BY sequence"
            ).fetchall(),
        )
        self.assertEqual("ok", connection.execute("PRAGMA quick_check").fetchone()[0])
        self.assertEqual("wal", connection.execute("PRAGMA journal_mode").fetchone()[0].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
