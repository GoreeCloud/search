"""Durable per-installation request ceiling for optional paid search APIs.

Reservations count attempted outbound requests before network egress. The ledger
contains only UTC dates and integers: never queries, credentials, or IPs. This
local ceiling is NOT an account-wide billing/plan safeguard.
"""
from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class BudgetUnavailable(RuntimeError):
    """Fail-closed local request accounting error."""


class BudgetExhausted(BudgetUnavailable):
    """The configured daily request ceiling has been reached."""


def _require_unsymlinked_ancestors(directory: Path) -> None:
    """Reject symlinked directory components, including non-immediate parents."""
    for ancestor in (directory, *directory.parents):
        if ancestor.is_symlink():
            raise BudgetUnavailable("Budget state directory ancestry must not contain symlinks")


def reserve_request(db_path: Path, daily_limit: int, *, now: datetime | None = None) -> None:
    """Atomically count an attempt before any billable network request.

    SQLite BEGIN IMMEDIATE serializes concurrent local processes sharing this
    file. Errors never permit a request. Do not refund ambiguous failures.
    """
    if type(daily_limit) is not int or not 1 <= daily_limit <= 10_000:
        raise BudgetUnavailable("Invalid configured request cap")
    if (not isinstance(db_path, Path) or not db_path.is_absolute()
            or ".." in db_path.parts):
        raise BudgetUnavailable("Budget state must use an absolute non-traversing path")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise BudgetUnavailable("Budget clock must have a timezone")
    day = current.astimezone(timezone.utc).date().isoformat()
    fd = None
    try:
        parent = db_path.parent
        _require_unsymlinked_ancestors(parent)
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _require_unsymlinked_ancestors(parent)
        parent_stat = parent.stat()
        if (not stat.S_ISDIR(parent_stat.st_mode)
                or stat.S_IMODE(parent_stat.st_mode) & 0o077
                or parent_stat.st_uid != os.getuid()):
            raise BudgetUnavailable("Budget state directory must be owner-private")
        fd = os.open(db_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        file_stat = os.fstat(fd)
        if (not stat.S_ISREG(file_stat.st_mode)
                or stat.S_IMODE(file_stat.st_mode) & 0o077
                or file_stat.st_uid != os.getuid()
                or db_path.is_symlink()):
            raise BudgetUnavailable("Budget ledger must be owner-private")
        os.close(fd)
        fd = None
        with closing(sqlite3.connect(str(db_path), timeout=5, isolation_level=None)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS daily_requests "
                    "(day TEXT PRIMARY KEY, reserved INTEGER NOT NULL CHECK(reserved >= 0))"
                )
                row = conn.execute(
                    "SELECT reserved FROM daily_requests WHERE day = ?", (day,)
                ).fetchone()
                if row is not None and row[0] >= daily_limit:
                    raise BudgetExhausted("Daily request ceiling reached")
                conn.execute(
                    "INSERT INTO daily_requests (day, reserved) VALUES (?, 1) "
                    "ON CONFLICT(day) DO UPDATE SET reserved = reserved + 1",
                    (day,),
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
    except BudgetUnavailable:
        raise
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        raise BudgetUnavailable("Cannot securely reserve a provider request") from exc
    finally:
        if fd is not None:
            os.close(fd)
