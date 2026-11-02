"""Private SQLite full-text catalog. No crawlers or third-party outbound requests."""
from __future__ import annotations

import json
import os
import stat
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from .links import public_https_url

MAX_IMPORT_BYTES = 2_000_000
MAX_RECORDS = 1000


class InvalidDocument(ValueError):
    """An input document did not satisfy the public catalog contract."""


def safe_url(value: object) -> str:
    accepted = public_https_url(value)
    if accepted is None:
        raise InvalidDocument("Only uncredentialed public HTTPS result URLs are supported")
    return accepted


def normalize_document(record: object) -> tuple[str, str, str, str]:
    if not isinstance(record, dict):
        raise InvalidDocument("Each document must be a JSON object")
    title = record.get("title")
    description = record.get("description")
    source = record.get("source", "curated")
    for name, value, cap in (
        ("title", title, 200),
        ("description", description, 2000),
        ("source", source, 60),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > cap:
            raise InvalidDocument(f"{name} must be nonempty text within {cap} characters")
        if any(ord(ch) < 32 and ch not in "\t\n" for ch in value):
            raise InvalidDocument(f"{name} contains unsupported control characters")
    return title.strip(), description.strip(), safe_url(record.get("url")), source.strip()


def _check_index_location(db_path: Path, *, check_parent: bool) -> None:
    """Refuse unsafe index paths without resolving symlinks or changing modes.

    The immediate parent protects private SQLite files and journaling.
    Ancestor symlinks and lexical traversal are refused, including for init.
    These checks do not defeat a hostile process with the same UID racing IO.
    """
    if not isinstance(db_path, Path) or not db_path.is_absolute() or ".." in db_path.parts:
        raise PermissionError("Index must use an absolute, non-traversing path")
    for directory in db_path.parents:
        if directory.is_symlink():
            raise PermissionError("Index directory ancestry may not contain symlinks")
    if db_path.is_symlink():
        raise PermissionError("Symlinked indexes are not allowed")
    if check_parent:
        parent = db_path.parent.stat()
        if (not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != os.getuid()
                or stat.S_IMODE(parent.st_mode) & 0o077):
            raise PermissionError("Index directory must be owner-private")


def _check_index_file(db_path: Path) -> None:
    try:
        info = db_path.lstat()
    except FileNotFoundError:
        raise FileNotFoundError("Index not initialized. Run 'init' first.") from None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise PermissionError("Index must be a regular, owner-private file")


def connect(db_path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    _check_index_location(db_path, check_parent=True)
    _check_index_file(db_path)
    # Explicit SQLite URI modes never create an index if it vanishes.
    # Normal local searches must not obtain write access to their source.
    mode = "ro" if read_only else "rw"
    conn = sqlite3.connect(db_path.as_uri() + f"?mode={mode}", timeout=5, uri=True)
    if read_only:
        conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def initialize(db_path: Path) -> None:
    _check_index_location(db_path, check_parent=False)
    db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _check_index_location(db_path, check_parent=True)
    if not db_path.exists():
        try:
            fd = os.open(db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
    _check_index_location(db_path, check_parent=True)
    _check_index_file(db_path)
    with closing(sqlite3.connect(db_path.as_uri() + "?mode=rw", uri=True)) as conn, conn:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS documents "
            "USING fts5(title, description, url UNINDEXED, source UNINDEXED)"
        )


def _reject_duplicate_json_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Refuse duplicate fields, including nested objects and ambiguous URLs."""
    record: dict[str, object] = {}
    for name, value in pairs:
        if name in record:
            raise InvalidDocument("Duplicate JSON field")
        record[name] = value
    return record


def _reject_json_constant(_value: str) -> None:
    raise InvalidDocument("Nonstandard JSON numeric value")


def _read_jsonl_snapshot(source_path: Path) -> str:
    """Read at most MAX_IMPORT_BYTES from one opened regular source file.

    The byte limit is enforced while reading, not just on a prior stat value.
    No FIFO/device access, symlink following, or unbounded line iteration.
    """
    if source_path.is_symlink():
        raise InvalidDocument("Symlinked import source refused")
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0))
    fd = os.open(source_path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise InvalidDocument("Import source must be a regular file")
        if info.st_size > MAX_IMPORT_BYTES:
            raise InvalidDocument("Import exceeds size limit")
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            raw = stream.read(MAX_IMPORT_BYTES + 1)
        if len(raw) > MAX_IMPORT_BYTES:
            raise InvalidDocument("Import exceeds size limit")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidDocument("Import source must use UTF-8") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def import_jsonl(db_path: Path, source_path: Path) -> int:
    snapshot = _read_jsonl_snapshot(source_path)
    documents: list[tuple[str, str, str, str]] = []
    # Split only on newline: str.splitlines() also splits Unicode separators
    # that could appear within JSON strings.
    for lineno, line in enumerate(snapshot.split("\n"), 1):
        if not line.strip():
            continue
        if len(documents) >= MAX_RECORDS:
            raise InvalidDocument("Import exceeds document limit")
        try:
            record = json.loads(
                line,
                object_pairs_hook=_reject_duplicate_json_fields,
                parse_constant=_reject_json_constant,
            )
            documents.append(normalize_document(record))
        except (json.JSONDecodeError, InvalidDocument) as exc:
            raise InvalidDocument(f"Invalid document at line {lineno}") from exc
    if not documents:
        raise InvalidDocument("Import contains no documents; original catalog preserved")
    with closing(connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM documents")
        conn.executemany(
            "INSERT INTO documents (title, description, url, source) VALUES (?, ?, ?, ?)",
            documents,
        )
    return len(documents)


def search(db_path: Path, query: str, limit: int = 12) -> list[dict[str, str]]:
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 160:
        raise ValueError("Query must contain between 1 and 160 characters")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("Limit must be between 1 and 20")
    terms = re.findall(r"\w+", query, flags=re.UNICODE)
    if not terms:
        return []
    # Construct a quoted FTS expression from bounded tokens, not raw user syntax.
    expression = " AND ".join('"' + term.replace('"', '""') + '"' for term in terms[:12])
    with closing(connect(db_path, read_only=True)) as conn:
        rows = conn.execute(
            "SELECT title, description, url, source FROM documents "
            "WHERE documents MATCH ? ORDER BY bm25(documents) LIMIT ?",
            (expression, limit),
        ).fetchall()
    return [dict(row) for row in rows]
