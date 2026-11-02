# GoreeCloud Search — Private backup, verification and recovery copies

**Status:** Original first-party Development capability in draft [PR #2](https://github.com/GoreeCloud/search/pull/2); no production deployment or automated backup schedule. The accepted on-disk format is a private SQLite FTS5 Search catalog supplied by the owner.

## Use in an authorized local development environment

A catalog must already exist and have only owner permissions. Choose a new, nonexistent output path inside an **owner-private (0700) directory**. These commands make no network connection and never enable external search:

```bash
python3 -m goreecloud_search --db /absolute/private/catalog.sqlite3 \
  backup --output /absolute/private/backups/catalog-2026-11-01.sqlite3

python3 -m goreecloud_search verify-backup \
  --input /absolute/private/backups/catalog-2026-11-01.sqlite3

# Makes a NEW catalog only. It does not replace an active index.
python3 -m goreecloud_search restore-copy \
  --input /absolute/private/backups/catalog-2026-11-01.sqlite3 \
  --output /absolute/private/restored-catalog.sqlite3
```

To use a recovered copy, **manually and deliberately** choose its pathname with `--db` when starting a new local session. Do not modify an existing active catalog in place. No deployment, scheduled backup, background process, service migration or in-place restore is performed by these commands.

## Safety properties

- Source catalogs must be absolute paths to owned, regular, owner-private files, without symlinks anywhere in their directory ancestry or at the final pathname; lexical `..` traversal components are refused. A read-only `PRAGMA quick_check` plus `documents` table count validates the Search schema.
- SQLite's online backup API creates a consistent snapshot of committed data, including data in a WAL journal.
- The destination must be an absolute new path without symlinked ancestors or lexical `..` traversal. The immediate parent directory must be owned by the current user and inaccessible to group/others. Missing parent directories are created owner-only when possible.
- Destination creation is exclusive (mode 0600); existing files or symbolic links, including dangling links, are refused without replacement. Failures attempt to remove only the newly created output inode.
- Snapshot and recovery-copy operations compare the document count to detect a mismatched snapshot. If the live source changes between the initial inspection and snapshot, the operation may fail closed; retrying after local writes stop is safer than silently accepting an inconsistent acceptance result.
- Verification reads only local storage, and command output contains document counts rather than titles, queries or credential values. **A snapshot contains the indexed documents and URLs** and therefore is sensitive; handle it as private data.

## Evidence

The enforced offline test suite includes twelve dedicated recovery contracts for private snapshot/verify, new-file restore preserving the original, corrupt/missing/non-Search inputs, existing/dangling symbolic links, unsafe parent folders, private permissions, relative path refusal, SQLite WAL commits, and an actual subprocess CLI round trip. CI runs on Python 3.11 and 3.12 with the no-skip gate.

A separate authorized Linux workstation ran the CLI sequence using a temporary two-document catalog and verified the original, snapshot and recovered file, all with 0600 file permissions. This was not a production backup or restore.

## Remaining operational acceptance

These commands are **not** encrypted offsite backups, routine rotation, retention policies, disaster recovery, restore-in-place, staging recovery or managed archival. The local disk and user account remain trusted. Lexical path and symlink-ancestor checks are fail-closed safeguards, not race-free protection against a hostile same-UID actor changing filesystem paths concurrently. Verify behavior under power loss, permissions, multiple filesystems and supported platforms before production acceptance. Implement an owner-approved backup schedule/retention/encryption/key-recovery plan before claiming operational reliability.

Do not declare Stable or Seal from this development capability alone.
