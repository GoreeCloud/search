# GoreeCloud Search — SQLite recovery qualification

**Development-only test candidate.** This work extends the isolated SQLite concurrency evidence in draft PR #12. It does not change the application, user data, provider engines, database configuration or production services.

## Tested failure scenarios

`tests/goreecloud/test_sqlite_recovery.py` creates a fresh temporary SQLite database and uses the actual `searx.sqlitedb.SQLiteAppl` adapter to initialize it. It verifies the following:

1. **Locked writer:** A first connection holds a write lock and an uncommitted row. A second connection attempts to write using a bounded timeout and must fail with `sqlite3.OperationalError`. After rollback, no partial row may appear and a new write must succeed. `PRAGMA quick_check` must return `ok`.
2. **Interrupted writer:** A disposable subprocess commits one row, opens a new write transaction, writes a second row without committing, and signals readiness. The test terminates only that owned child process, creates a new application adapter, and verifies that the committed row survives while the uncommitted row does not. The restarted connection must report WAL mode and a clean SQLite integrity check.

This is an adversarial test of SQLite behavior and the initialized application schema on the test host, **not** a claim of resilience against power loss, filesystem corruption, database migration failures or production host storage faults. The subprocess uses only test-generated rows and is force-reaped by the parent; nothing touches GoreeCloud production databases or VPS processes.

## Required remaining gates

- Reproduce on the target Python/SQLite ABI, storage mount and container orchestration under supervised concurrency.
- Validate production-equivalent cache startup, idle transaction recovery, WAL checkpoint/shutdown, multiprocess races, disk-full or read-only filesystem, verified backups and clean restores.
- Keep existing SQLite threading warnings visible and evaluate their runtime significance; never override SQLite threading protection or simply hide the warnings.
- Complete public Identity and rate-limiter requirements, approved Brave/Startpage live availability checks, Glaze mobile accessibility acceptance, security review, staging rollback and owner authorization.

**Rollback:** remove the test and qualification document through reviewed development changes. No migration, data restoration or service action is necessary because only temporary test databases are created.
