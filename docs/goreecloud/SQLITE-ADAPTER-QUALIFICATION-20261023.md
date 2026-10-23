# Search SQLite adapter — isolated concurrency and recovery qualification

**Date:** October 23, 2026

**Scope:** Development-source tests only; no runtime, provider, user data, release or deployment change
**Disposition:** Partial adapter evidence; Seal/Anchor storage and recovery gates remain open

## Why this is included

The independent, still-draft Search [PR #12](https://github.com/GoreeCloud/search/pull/12)
and [PR #13](https://github.com/GoreeCloud/search/pull/13) contain useful SQLite
concurrency and interrupted-writer regressions but their exact commit heads
are not ancestors of the integrated Development source. This controlled
Development test file reproduces the four intended scenarios against the
**current** `searx.sqlitedb.SQLiteAppl` adapter, with a fresh temporary SQLite
database for each case. It does not cherry-pick their old branch history or
silently close, retarget or merge the original PRs.

`tests/goreecloud/test_sqlite_adapter_qualification.py` checks:

1. Six concurrent worker threads use distinct connections and commit 144
   unique rows, followed by `PRAGMA quick_check`.
2. When the SQLite runtime advertises DB-API `threadsafety == 1`, use of a
   connection from another thread is rejected without a database write.
   On a serialized runtime, this specific condition is **skipped**, not passed.
3. A second writer cannot bypass a held write lock. After the lock is rolled
   back, the uncommitted row is absent and a later insert succeeds.
4. A disposable child process is killed after writing one committed and one
   uncommitted row. Reopening the application adapter preserves only the
   committed row and confirms WAL and `quick_check`.

The tests never open Search's configured user/cache database, contact
providers, change a database schema in any running deployment, or disable
upstream SQLite threading diagnostics. A green test provides **host-runtime
behavioral evidence** only; it does not establish durability under power
loss, disk-full faults, file corruption, real workload contention or a
production-equivalent database mount.

## Repeatable local verification

With the repository's pinned Python dependencies installed:

```bash
python3 -m unittest discover -s tests/goreecloud \
  -p test_sqlite_adapter_qualification.py -v
```

Required integration checks are exact-head Foundation and Native Search
workflows and test execution on representative supported Python/SQLite and
storage environments. Before either original PR can be classified as
functionally superseded, compare their exact scenario assertions with this
file and verify the integrated Development head, not merely this draft.

## Remaining gates

- Confirm actual intended platform SQLite ABI, compile-time threadsafety and
  storage behavior; retain expected diagnostic warnings.
- Test cache startup/shutdown, WAL checkpoint and concurrent request loads,
  multi-process races, disk-full/read-only storage, and migration behavior.
- Demonstrate a verified backup **and** clean restore to an isolated target.
- Complete source-to-image and deployment provenance, privacy/security,
  GC UI, native-platform and all applicable nine-system acceptance before a
  frozen Seal candidate or supported Anchor release.

**Rollback:** Remove this test/document through reviewed Development source
control. There is no production data migration or deployment to roll back.
