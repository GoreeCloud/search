# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local, owned search index: SQLite FTS5, deterministic ranking and no provider egress."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str
    excerpt: str
    host: str
    indexed_at: str
    score: float


def clean_query(query: object) -> list[str]:
    if not isinstance(query, str) or not 1 <= len(query) <= 256:
        raise ValueError('Query must contain 1 to 256 characters')
    terms = re.findall(r'[^\W_]+', query, re.UNICODE)
    if not terms or len(terms) > 16 or any(len(term) > 64 for term in terms):
        raise ValueError('Query must contain 1 to 16 bounded words')
    return terms


class SearchIndex:
    """A transactional private index; input documents are explicitly approved by caller."""

    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        # The development API uses one synchronous HTTPServer worker, not a pool.
        # Do not share this connection with parallel workers or an active crawler.
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript('''
          PRAGMA foreign_keys=ON;
          CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE,
            host TEXT NOT NULL, title TEXT NOT NULL,
            body TEXT NOT NULL, indexed_at TEXT NOT NULL
          );
          CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
            title, body, content='pages', content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
          );
          CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
            INSERT INTO pages_fts(rowid,title,body) VALUES(new.id,new.title,new.body);
          END;
          CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts,rowid,title,body)
            VALUES('delete',old.id,old.title,old.body);
          END;
          CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts,rowid,title,body)
            VALUES('delete',old.id,old.title,old.body);
            INSERT INTO pages_fts(rowid,title,body) VALUES(new.id,new.title,new.body);
          END;
        ''')

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> SearchIndex:
        return self

    def __exit__(self, *_unused: object) -> None:
        self.close()

    def add(self, *, url: str, title: str, body: str) -> None:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or parsed.port not in (None, 443)):
            raise ValueError('Only canonical HTTPS document URLs are indexable')
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        if (address is not None or parsed.hostname in ('localhost', 'localdomain')
                or parsed.hostname.endswith(('.local', '.localhost', '.internal'))):
            raise ValueError('Index URLs must be public HTTPS hostnames')
        if not isinstance(title, str) or not isinstance(body, str):
            raise TypeError('Document title and body must be text')
        title = ' '.join(title.split())[:300]
        body = ' '.join(body.split())[:200_000]
        if not title or not body:
            raise ValueError('Documents must have a title and content')
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        with self.connection:
            self.connection.execute('''
              INSERT INTO pages(url,host,title,body,indexed_at) VALUES(?,?,?,?,?)
              ON CONFLICT(url) DO UPDATE SET host=excluded.host,title=excluded.title,
                body=excluded.body,indexed_at=excluded.indexed_at
            ''', (url, parsed.hostname.lower(), title, body, now))

    def remove(self, url: str) -> bool:
        """Immediately remove a document and its full-text entries, e.g. on takedown."""
        with self.connection:
            cursor = self.connection.execute('DELETE FROM pages WHERE url=?', (url,))
        return cursor.rowcount > 0

    def count(self) -> int:
        return self.connection.execute('SELECT COUNT(*) FROM pages').fetchone()[0]

    def search(self, query: object, *, limit: int = 10) -> list[SearchHit]:
        terms = clean_query(query)
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError('Result limit must be from 1 to 20')
        # Quote each term separately so FTS5 syntax never comes from a client.
        match = ' AND '.join('"' + term.replace('"', '""') + '"' for term in terms)
        rows = self.connection.execute('''
          SELECT p.url,p.title,p.body,p.host,p.indexed_at,
                 bm25(pages_fts,5.0,1.0) AS relevance
          FROM pages_fts JOIN pages AS p ON p.id=pages_fts.rowid
          WHERE pages_fts MATCH ? ORDER BY relevance ASC, p.url ASC LIMIT ?
        ''', (match, limit)).fetchall()
        return [SearchHit(
            url=r['url'], title=r['title'], excerpt=r['body'][:240],
            host=r['host'], indexed_at=r['indexed_at'], score=round(float(-r['relevance']), 6),
        ) for r in rows]
