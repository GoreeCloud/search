"""Private, non-destructive snapshot and recovery-copy operations for local Search.

The SQLite online backup API preserves a consistent source snapshot, including
committed WAL data. No output overwrite, network connection, or schema upgrade.
"""
from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path



class RecoveryError(ValueError):
    """A catalog snapshot is unsafe, missing, or invalid."""


def _check_directory_ancestry(path: Path) -> None:
    """Refuse path traversal or symlinks in private catalog ancestry."""
    if ".." in path.parts:
        raise RecoveryError("Catalog path traversal is not permitted")
    for directory in path.parents:
        if directory.is_symlink():
            raise RecoveryError("Catalog directory ancestry must not use symlinks")


def _open_source_readonly(path: Path) -> sqlite3.Connection:
    """Open an existing catalog in SQLite read-only mode from the first IO."""
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    connection.execute("PRAGMA query_only = ON")
    return connection


def inspect_catalog(path: Path) -> int:
    """Validate a private catalog, return document count; never modify it."""
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        raise RecoveryError("Catalog path must be an absolute non-symlink path")
    _check_directory_ancestry(path)
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise RecoveryError("Catalog file must be owner-private and regular")
        with closing(_open_source_readonly(path)) as db:
            integrity = db.execute("PRAGMA quick_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise RecoveryError("Catalog integrity check failed")
            row = db.execute("SELECT COUNT(*) FROM documents").fetchone()
            if row is None or not isinstance(row[0], int) or row[0] < 0:
                raise RecoveryError("Catalog record count unavailable")
            return row[0]
    except RecoveryError:
        raise
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise RecoveryError("Catalog is inaccessible or not a valid Search index") from exc


def snapshot_catalog(source: Path, destination: Path) -> int:
    """Copy a committed SQLite snapshot to a brand-new private file.

    Never overwrites an existing destination, follows destination symlinks or
    modifies the original. The destination parent must be an owned 0700 folder
    (including newly created folders) to avoid exposing private index content.
    """
    source_count = inspect_catalog(source)
    if not isinstance(destination, Path) or not destination.is_absolute():
        raise RecoveryError("Destination must be an absolute local path")
    if destination.is_symlink():
        raise RecoveryError("Symlinked destination refused")
    _check_directory_ancestry(destination)
    parent = destination.parent
    try:
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _check_directory_ancestry(destination)
        info = parent.stat()
        if (not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise RecoveryError("Destination folder must be owner-private")
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(destination, flags, 0o600)
    except FileExistsError as exc:
        raise RecoveryError("Destination already exists; refusing overwrite") from exc
    except RecoveryError:
        raise
    except OSError as exc:
        raise RecoveryError("Cannot safely create private snapshot") from exc

    created = os.fstat(fd)
    os.close(fd)
    try:
        with closing(_open_source_readonly(source)) as original:
            with closing(sqlite3.connect(str(destination), timeout=5)) as out:
                original.backup(out)
        verified_count = inspect_catalog(destination)
        if verified_count != source_count:
            raise RecoveryError("Snapshot record count mismatch")
        return verified_count
    except BaseException:
        # Only remove the file that we created; never remove a swapped target.
        try:
            current = destination.lstat()
            if (stat.S_ISREG(current.st_mode) and current.st_dev == created.st_dev
                    and current.st_ino == created.st_ino):
                destination.unlink()
        except OSError:
            pass
        raise
