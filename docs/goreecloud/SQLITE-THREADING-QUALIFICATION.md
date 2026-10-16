# GoreeCloud Search — SQLite concurrency release gate

**Environment:** Development-only qualification at branch `test/search-sqlite-qualification-20261016`, stacked on draft PR #11. This does **not** establish Stable, staging, or production readiness.

## What the evidence does and does not prove

Upstream `searx/sqlitedb.py` detects the Python SQLite library's DB-API threadsafety level and emits its usual multi-thread warning/error if the runtime does not report fully serialized mode. The implementation uses thread-local `DBSession` connections and `check_same_thread=True` in multi-thread mode. Suppressing this diagnostic or forcing serialized mode would conceal, rather than solve, risk.

The isolated test `tests/goreecloud/test_sqlite_concurrency.py` uses a fresh temporary database and the application's real `SQLiteAppl` adapter. It asserts:

- Six simultaneous threads independently acquire their own SQLite connections.
- Each thread commits 24 unique inserts; all 144 records remain readable.
- The journal mode is WAL.
- In DB-API multi-thread mode, using a connection from another thread raises `sqlite3.ProgrammingError` and writes no row.
- The test does not contact Brave Search, Startpage, Search user databases, a network endpoint, or the production VPS.

**Observed on the Development laptop on 2026-10-16:** Both focused tests passed, and ten consecutive repetitions passed; the full GoreeCloud regression suite passed 135 tests. The upstream multi-thread warnings still occurred, as expected. Refer to the commit's exact-head GitHub Actions Python 3.10/3.12 status for CI evidence; do not infer success from local results.

## Required acceptance before release

- Repeat the test on the actual intended deployment operating system, Python runtime, SQLite library and data-storage device; record `sqlite3.threadsafety`, SQLite library version and Python ABI.
- Validate the real app's cache operations, concurrent page requests, WAL checkpoint behavior, disk-full/locked-database recovery, startup/shutdown, multi-process reuse and migration/backup-restoration with synthetic data.
- Inspect the SQLite underlying implementation for concurrency/migration risks under independent security review; do not disable warnings to pass a check.
- Verify authentication and Valkey-backed rate limiting before public exposure, privacy boundaries, provider-specific availability, official Glaze accessibility review, staging rollback, observability and owner's release approval.

**Rollback:** remove this isolated test file and documentation in a reviewed development change; no database migration, configuration switch or new dependency is necessary. Keep PRs unmerged until all applicable gates pass.
