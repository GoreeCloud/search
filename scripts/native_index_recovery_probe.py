#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create and restore-probe an *offline* owned Search SQLite index snapshot.

No running service is stopped, no existing database is replaced, no network is
used, and successful evidence is not Everkeep or production recovery acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from urllib.parse import quote


MAX_INPUT_BYTES = 512 * 1024 * 1024
SQLITE_HEADER = b"SQLite format 3\x00"


class RecoveryBlocked(Exception):
    """A reversible local snapshot/restore probe is unsafe or invalid."""


def _reject_symlinks(path: Path) -> None:
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise RecoveryBlocked("symlink paths cannot be used for recovery evidence")


def _source(path: Path) -> None:
    _reject_symlinks(path)
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise RecoveryBlocked("source is not a regular SQLite database")
        with path.open("rb") as stream:
            if stream.read(16) != SQLITE_HEADER:
                raise RecoveryBlocked("source is not a regular SQLite database")
        if not 0 < info.st_size <= MAX_INPUT_BYTES:
            raise RecoveryBlocked("source index is outside the bounded test size")
    except FileNotFoundError as error:
        raise RecoveryBlocked("source database is missing") from error


def _new_output(path: Path, used: set[Path]) -> None:
    _reject_symlinks(path)
    if path in used:
        raise RecoveryBlocked("backup and restore-probe targets must differ")
    if not path.parent.is_dir():
        raise RecoveryBlocked("output parent must already exist")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise RecoveryBlocked("existing output will never be overwritten") from error
    os.close(descriptor)
    used.add(path)


def _open_readonly(path: Path) -> sqlite3.Connection:
    url = "file:" + quote(str(path.absolute()), safe="/") + "?mode=ro"
    connection = sqlite3.connect(url, uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _assert_owned_index(connection: sqlite3.Connection) -> int:
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RecoveryBlocked("SQLite integrity check failed")
    objects = dict(connection.execute("SELECT name,type FROM sqlite_master WHERE name IN "
                                      "('pages','pages_fts','pages_ai','pages_ad','pages_au')"))
    if objects != {"pages": "table", "pages_fts": "table", "pages_ai": "trigger",
                   "pages_ad": "trigger", "pages_au": "trigger"}:
        raise RecoveryBlocked("source is not a complete owned Search index")
    fts_definition = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name='pages_fts'"
    ).fetchone()[0]
    if not isinstance(fts_definition, str) or not re.match(
        r"^CREATE\s+VIRTUAL\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?pages_fts\s+USING\s+fts5\s*\(",
        fts_definition, re.IGNORECASE,
    ):
        raise RecoveryBlocked("owned pages_fts must be an actual FTS5 virtual table")
    count = connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    if count < 0:
        raise RecoveryBlocked("invalid index document count")
    return count


def _verify_fts(path: Path, expected_count: int) -> None:
    # The FTS5 integrity-check command validates index contents against its
    # external-content table. It may write bookkeeping to the *probe only*.
    with sqlite3.connect(path) as connection:
        if _assert_owned_index(connection) != expected_count:
            raise RecoveryBlocked("document count changed across backup/restore")
        connection.execute("INSERT INTO pages_fts(pages_fts) VALUES('integrity-check')")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exercise(source: Path, backup: Path, restored: Path) -> dict:
    """Create two never-overwritten files; test only those disposable copies."""
    source, backup, restored = source.absolute(), backup.absolute(), restored.absolute()
    if len({source, backup, restored}) != 3:
        raise RecoveryBlocked("source, backup and restore probe must be distinct")
    _source(source)
    created: set[Path] = set()
    try:
        _new_output(backup, created)
        _new_output(restored, created)
        with _open_readonly(source) as live:
            _assert_owned_index(live)
            with sqlite3.connect(backup) as snapshot:
                live.backup(snapshot, pages=32, sleep=0.05)
        with _open_readonly(backup) as saved:
            count = _assert_owned_index(saved)
            with sqlite3.connect(restored) as probe:
                saved.backup(probe, pages=32, sleep=0.05)
        _verify_fts(restored, count)
        # No URLs, search terms, document text or source filesystem paths.
        return {
            "schema": "goreecloud.search.native-index-recovery-probe.v1",
            "status": "synthetic_or_local_disposable_restore_probe_passed",
            "document_count": count,
            "backup_sha256": _sha256(backup),
            "restored_sha256": _sha256(restored),
            "not_evaluated": ["everkeep_platform_integration", "live_service_consistency",
                              "remote_backup_or_restore", "secrets_and_encryption",
                              "real_rollback_and_os_service_lifecycle", "seal_and_anchor"],
        }
    except (sqlite3.DatabaseError, OSError, RecoveryBlocked) as error:
        # Only files exclusively created by this invocation are removed. Never
        # unlink an existing user file or the source index on failure.
        for candidate in created:
            try:
                candidate.unlink()
            except OSError:
                pass
        if isinstance(error, RecoveryBlocked):
            raise
        raise RecoveryBlocked("offline index snapshot or restore validation failed") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--restore-probe", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(exercise(args.source, args.backup, args.restore_probe),
                         indent=2, sort_keys=True))
    except RecoveryBlocked as error:
        parser.exit(2, "NATIVE_INDEX_RECOVERY_BLOCKED: " + str(error) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
