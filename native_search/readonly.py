# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only FTS5 adapter for an explicitly chosen native Development source.

No network, crawling, provider fallback, cookies or query logging. The corpus
must be a separately reviewed snapshot. Never open a writable SearchIndex
from the federated web application's request worker.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from urllib.parse import quote

from .index import SearchHit, clean_query


def read_native_results(database: str | Path, query: object, *, limit: int = 10) -> list[SearchHit]:
    terms = clean_query(query)
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('Native result limit must be from 1 to 20')
    if not isinstance(database, (str, Path)):
        raise ValueError('An absolute native index path is required')
    raw = Path(database)
    if not raw.is_absolute() or raw.is_symlink() or not raw.is_file():
        raise ValueError('Native Development index must be an existing regular file')
    # URI encoding prevents a filename with ? or # from changing SQLite flags.
    address = 'file:' + quote(str(raw), safe='/') + '?mode=ro'
    match = ' AND '.join('"' + term.replace('"', '""') + '"' for term in terms)
    with closing(sqlite3.connect(address, uri=True, timeout=2.0)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        rows = connection.execute("""
            SELECT p.url, p.title, p.body, p.host, p.indexed_at,
                   bm25(pages_fts, 5.0, 1.0) AS relevance
              FROM pages_fts
              JOIN pages AS p ON p.id = pages_fts.rowid
             WHERE pages_fts MATCH ?
             ORDER BY relevance ASC, p.url ASC LIMIT ?
        """, (match, limit)).fetchall()
    return [
        SearchHit(
            url=row['url'], title=row['title'], excerpt=row['body'][:240],
            host=row['host'], indexed_at=row['indexed_at'],
            score=round(float(-row['relevance']), 6),
        )
        for row in rows
    ]
