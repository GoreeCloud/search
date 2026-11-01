"""Disposable concurrency and interrupted-writer checks for the real SQLiteAppl.

These are narrow Development adapter regressions, not live storage, restore, or
power-loss acceptance. No configured Search database, provider or network is used.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

from searx.sqlitedb import SQLiteAppl


class QualificationStore(SQLiteAppl):
    DB_SCHEMA = 1
    DDL_CREATE_TABLES = {
        "qualification_events": (
            "CREATE TABLE IF NOT EXISTS qualification_events "
            "(worker INTEGER NOT NULL, sequence INTEGER NOT NULL, "
            "PRIMARY KEY (worker, sequence))"
        )
    }


class SQLiteAdapterQualification(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gc-search-sqlite-qualification-")
        self.addCleanup(temporary.cleanup)
        self.db_path = str(Path(temporary.name) / "qualification.sqlite3")
        self.app = QualificationStore(self.db_path)
        self.assertEqual("wal", self.app.DB.execute("PRAGMA journal_mode").fetchone()[0].lower())

    def test_six_threads_commit_144_rows_without_sharing_connections(self):
        self.assertNotEqual(0, sqlite3.threadsafety, "Single-thread SQLite cannot qualify")
        workers, writes = 6, 24
        barrier = threading.Barrier(workers, timeout=15)

        def writer(index):
            connection = self.app.DB
            barrier.wait()
            for sequence in range(writes):
                with connection:
                    connection.execute(
                        "INSERT INTO qualification_events(worker,sequence) VALUES (?,?)",
                        (index, sequence),
                    )
            count = connection.execute(
                "SELECT COUNT(*) FROM qualification_events WHERE worker=?", (index,)
            ).fetchone()[0]
            return threading.get_ident(), id(connection), count

        with ThreadPoolExecutor(max_workers=workers) as executor:
            observations = list(executor.map(writer, range(workers)))

        self.assertEqual(workers, len({thread_id for thread_id, _, _ in observations}))
        self.assertEqual(workers, len({connection_id for _, connection_id, _ in observations}))
        self.assertTrue(all(count == writes for _, _, count in observations))
        self.assertEqual(
            workers * writes,
            self.app.DB.execute("SELECT COUNT(*) FROM qualification_events").fetchone()[0],
        )
        self.assertEqual("ok", self.app.DB.execute("PRAGMA quick_check").fetchone()[0])

    def test_multithread_mode_rejects_cross_thread_connection_use(self):
        if sqlite3.threadsafety != 1:
            self.skipTest("Cross-thread connection rejection applies to SQLite multithread mode")
        self.assertTrue(self.app.SQLITE_CONNECT_ARGS["check_same_thread"])
        connection = self.app.DB

        def unsafe_write():
            try:
                connection.execute(
                    "INSERT INTO qualification_events(worker,sequence) VALUES (99,99)"
                )
            except Exception as error:
                return error
            return None

        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(unsafe_write).result(timeout=8)
        self.assertIsInstance(result, sqlite3.ProgrammingError)
        self.assertEqual(0, self.app.DB.execute("SELECT COUNT(*) FROM qualification_events").fetchone()[0])

    def test_locked_writer_times_out_without_partial_commit_then_recovers(self):
        lock_owner = sqlite3.connect(self.db_path, isolation_level=None, timeout=1)
        blocked = sqlite3.connect(self.db_path, isolation_level=None, timeout=0.2)
        try:
            lock_owner.execute("BEGIN IMMEDIATE")
            lock_owner.execute("INSERT INTO qualification_events VALUES (1,1)")
            with self.assertRaises(sqlite3.OperationalError) as failure:
                blocked.execute("INSERT INTO qualification_events VALUES (2,1)")
            self.assertIn("locked", str(failure.exception).lower())
            lock_owner.rollback()
            self.assertEqual(0, self.app.DB.execute("SELECT COUNT(*) FROM qualification_events").fetchone()[0])
            blocked.execute("INSERT INTO qualification_events VALUES (2,1)")
            self.assertEqual(
                [(2, 1)],
                self.app.DB.execute(
                    "SELECT worker, sequence FROM qualification_events ORDER BY worker"
                ).fetchall(),
            )
            self.assertEqual("ok", self.app.DB.execute("PRAGMA quick_check").fetchone()[0])
        finally:
            if lock_owner.in_transaction:
                lock_owner.rollback()
            blocked.close()
            lock_owner.close()

    def test_killed_writer_preserves_committed_row_and_rejects_uncommitted_row(self):
        child_code = (
            "import sqlite3,sys,time\n"
            "conn=sqlite3.connect(sys.argv[1], timeout=2)\n"
            "conn.execute('PRAGMA journal_mode=WAL')\n"
            "conn.execute('INSERT INTO qualification_events VALUES (3,1)')\n"
            "conn.commit()\n"
            "conn.execute('BEGIN IMMEDIATE')\n"
            "conn.execute('INSERT INTO qualification_events VALUES (3,2)')\n"
            "print('READY', flush=True)\n"
            "time.sleep(60)\n"
        )
        child = subprocess.Popen(
            [sys.executable, "-u", "-c", child_code, self.db_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertIsNotNone(child.stdout)
            ready, _, _ = select.select([child.stdout], [], [], 10)
            self.assertTrue(ready, "Child writer did not reach transaction boundary")
            self.assertEqual("READY", child.stdout.readline().strip())
            self.assertIsNone(child.poll(), "Child stopped before controlled interruption")
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)

        reopened = QualificationStore(self.db_path)
        self.assertEqual(
            [(3, 1)],
            reopened.DB.execute(
                "SELECT worker, sequence FROM qualification_events ORDER BY sequence"
            ).fetchall(),
        )
        self.assertEqual("wal", reopened.DB.execute("PRAGMA journal_mode").fetchone()[0].lower())
        self.assertEqual("ok", reopened.DB.execute("PRAGMA quick_check").fetchone()[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
