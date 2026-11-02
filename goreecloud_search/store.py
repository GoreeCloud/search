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


def connect(db_path: Path) -> sqlite3.Connection:
    if db_path.is_symlink():
        raise PermissionError("Symlinked indexes are not allowed")
    if not db_path.is_file():
        raise FileNotFoundError("Index not initialized. Run 'init' first.")
    if stat.S_IMODE(db_path.stat().st_mode) & 0o077:
        raise PermissionError("Index permissions must restrict access to its owner")
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def initialize(db_path: Path) -> None:
    # Match connect(): never initialize through an existing or dangling symlink.
    if db_path.is_symlink():
        raise PermissionError("Symlinked indexes are not allowed")
    db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not db_path.exists():
        try:
            fd = os.open(db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
    if db_path.is_symlink() or not db_path.is_file():
        raise PermissionError("Index must be a regular file, not a symlink")
    if stat.S_IMODE(db_path.stat().st_mode) & 0o077:
        raise PermissionError("Index permissions must restrict access to its owner")
    with closing(sqlite3.connect(str(db_path))) as conn, conn:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS documents "
            "USING fts5(title, description, url UNINDEXED, source UNINDEXED)"
        )


def import_jsonl(db_path: Path, source_path: Path) -> int:
    if source_path.stat().st_size > MAX_IMPORT_BYTES:
        raise InvalidDocument("Import exceeds size limit")
    documents: list[tuple[str, str, str, str]] = []
    with source_path.open("r", encoding="utf-8") as stream:
        for lineno, line in enumerate(stream, 1):
            if not line.strip():
                continue
            if len(documents) >= MAX_RECORDS:
                raise InvalidDocument("Import exceeds document limit")
            try:
                documents.append(normalize_document(json.loads(line)))
            except (json.JSONDecodeError, InvalidDocument) as exc:
                raise InvalidDocument(f"Invalid document at line {lineno}") from exc
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
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT title, description, url, source FROM documents "
            "WHERE documents MATCH ? ORDER BY bm25(documents) LIMIT ?",
            (expression, limit),
        ).fetchall()
    return [dict(row) for row in rows]
