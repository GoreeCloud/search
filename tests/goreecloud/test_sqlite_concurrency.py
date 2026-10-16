"""Development-only SQLite threading qualification for GoreeCloud Search.

The fixture uses a new temporary database, never the Search database or
provider caches. An all-green result is narrow adapter evidence, not a
production database acceptance or a reason to hide upstream warnings.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from searx.sqlitedb import SQLiteAppl


class IsolatedSQLiteProbe(SQLiteAppl):
    DDL_CREATE_TABLES = {
        "goreecloud_qualification": (
            "CREATE TABLE IF NOT EXISTS goreecloud_qualification "
            "(worker INTEGER NOT NULL, counter INTEGER NOT NULL, "
            "PRIMARY KEY (worker, counter))"
        ),
    }
    DB_SCHEMA = 1


class SearchSQLiteConcurrencyQualification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gc-search-sqlite-test-")
        self.addCleanup(self.temp.cleanup)
        self.db_path = str(Path(self.temp.name) / "test.sqlite3")
        self.app = IsolatedSQLiteProbe(self.db_path)
        self.assertEqual(0, self.app.DB.execute(
            "SELECT COUNT(*) FROM goreecloud_qualification"
        ).fetchone()[0])

    def test_six_threads_have_independent_connections_and_144_commits(self):
        self.assertNotEqual(
            0, sqlite3.threadsafety,
            "A single-thread SQLite library is not approved for this test",
        )
        worker_count, writes_per_worker = 6, 24
        barrier = threading.Barrier(worker_count, timeout=15)

        def write_in_worker(index):
            # Must acquire in the current thread, never pass connections around.
            conn = self.app.DB
            barrier.wait()
            for counter in range(writes_per_worker):
                with conn:
                    conn.execute(
                        "INSERT INTO goreecloud_qualification(worker,counter) VALUES (?,?)",
                        (index, counter),
                    )
            result = conn.execute(
                "SELECT COUNT(*) FROM goreecloud_qualification WHERE worker=?",
                (index,),
            ).fetchone()[0]
            return threading.get_ident(), id(conn), result

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            results = list(executor.map(write_in_worker, range(worker_count)))
        self.assertEqual(worker_count, len(set(a for a, _, _ in results)))
        self.assertEqual(
            worker_count,
            len(set(b for _, b, _ in results)),
            "Connections are unexpectedly shared across worker threads",
        )
        self.assertTrue(all(n == writes_per_worker for _, _, n in results))
        conn = self.app.DB
        self.assertEqual(
            worker_count * writes_per_worker,
            conn.execute("SELECT COUNT(*) FROM goreecloud_qualification").fetchone()[0],
        )
        self.assertEqual("wal", conn.execute("PRAGMA journal_mode").fetchone()[0].lower())

    def test_multi_thread_sqlite_rejects_cross_thread_connection_use(self):
        if sqlite3.threadsafety != 1:
            self.skipTest("SQLite cross-thread rejection applies to multi-thread mode")
        self.assertTrue(self.app.SQLITE_CONNECT_ARGS["check_same_thread"])
        conn = self.app.DB

        def misuse_connection():
            try:
                conn.execute(
                    "INSERT INTO goreecloud_qualification(worker,counter) VALUES (999,999)"
                )
            except Exception as exc:
                return exc
            return None

        with ThreadPoolExecutor(max_workers=1) as executor:
            failure = executor.submit(misuse_connection).result(timeout=8)
        self.assertIsInstance(failure, sqlite3.ProgrammingError)
        self.assertEqual(
            0,
            self.app.DB.execute(
                "SELECT COUNT(*) FROM goreecloud_qualification"
            ).fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
