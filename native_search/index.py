# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local, owned search index: SQLite FTS5, deterministic ranking and no provider egress."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import re
import sqlite3
import unicodedata
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


@dataclass(frozen=True)
class ImageHit:
    """First-party indexed image metadata; image bytes are never fetched."""

    page_url: str
    media_url: str
    title: str
    description: str
    rights_evidence: str
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
          CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY,
            media_url TEXT NOT NULL UNIQUE,
            page_url TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            rights_evidence TEXT NOT NULL,
            indexed_at TEXT NOT NULL
          );
          CREATE VIRTUAL TABLE IF NOT EXISTS images_fts USING fts5(
            title, description, content='images', content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
          );
          CREATE TRIGGER IF NOT EXISTS images_ai AFTER INSERT ON images BEGIN
            INSERT INTO images_fts(rowid,title,description)
            VALUES(new.id,new.title,new.description);
          END;
          CREATE TRIGGER IF NOT EXISTS images_ad AFTER DELETE ON images BEGIN
            INSERT INTO images_fts(images_fts,rowid,title,description)
            VALUES('delete',old.id,old.title,old.description);
          END;
          CREATE TRIGGER IF NOT EXISTS images_au AFTER UPDATE ON images BEGIN
            INSERT INTO images_fts(images_fts,rowid,title,description)
            VALUES('delete',old.id,old.title,old.description);
            INSERT INTO images_fts(rowid,title,description)
            VALUES(new.id,new.title,new.description);
          END;
        ''')

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> SearchIndex:
        return self

    def __exit__(self, *_unused: object) -> None:
        self.close()

    @staticmethod
    def _prepare_document(url: str, title: str, body: str) -> tuple[str, str, str, str, str]:
        if not isinstance(url, str) or len(url) > 2000:
            raise ValueError('Invalid canonical document URL')
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError('Malformed canonical document URL') from exc
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or port not in (None, 443) or any(ord(x) <= 32 for x in url)):
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
        return url, parsed.hostname.lower(), title, body, now

    def add_many(self, documents: list[tuple[str, str, str]]) -> int:
        """Validate bounded batch before mutation, then commit FTS5 writes atomically."""
        if not isinstance(documents, list) or not 1 <= len(documents) <= 100:
            raise ValueError('Document batch must contain 1 to 100 items')
        prepared = [self._prepare_document(*entry) for entry in documents]
        with self.connection:
            self.connection.executemany('''
              INSERT INTO pages(url,host,title,body,indexed_at) VALUES(?,?,?,?,?)
              ON CONFLICT(url) DO UPDATE SET host=excluded.host,title=excluded.title,
                body=excluded.body,indexed_at=excluded.indexed_at
            ''', prepared)
        return len(prepared)

    def add(self, *, url: str, title: str, body: str) -> None:
        self.add_many([(url, title, body)])

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

    @staticmethod
    def _public_image_url(value: object) -> bool:
        """Validate display-only HTTPS metadata, never perform DNS or fetching.

        A stricter subset of media proxy inputs intentionally excludes token
        query strings, fragments and private hosts from locally stored images.
        Network egress protections are separately necessary if fetching is
        ever implemented; this local-only index cannot fetch image bytes.
        """
        if (not isinstance(value, str) or not 0 < len(value) <= 2000
                or '\\' in value or any(ord(ch) <= 32 or ord(ch) == 127 for ch in value)):
            return False
        try:
            target = urlsplit(value)
            host, port = target.hostname, target.port
            if (target.scheme != 'https' or not host or target.username is not None
                    or target.password is not None or port not in (None, 443)
                    or target.query or target.fragment or '%' in target.netloc):
                return False
            try:
                ipaddress.ip_address(host)
                return False
            except ValueError:
                pass
            ascii_host = host.encode('idna').decode('ascii').lower()
            if (ascii_host.endswith('.') or len(ascii_host) > 253
                    or '.' not in ascii_host or ascii_host.startswith('.')):
                return False
            labels = ascii_host.split('.')
            if (any(not 1 <= len(label) <= 63
                    or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', label)
                    for label in labels)
                    or labels[-1] in {'local', 'localhost', 'internal', 'lan', 'invalid',
                                      'test', 'example', 'onion', 'arpa'}
                    or not re.fullmatch(r'[a-z]{2,63}|xn--[a-z0-9-]+', labels[-1])):
                return False
            return True
        except (UnicodeError, ValueError):
            return False

    @classmethod
    def _prepare_image(cls, page_url: str, media_url: str, title: str,
                       description: str, rights_evidence: str) -> tuple[str, str, str, str, str, str]:
        if not cls._public_image_url(page_url) or not cls._public_image_url(media_url):
            raise ValueError('Images require canonical public HTTPS page and media URLs')
        if not isinstance(title, str) or not isinstance(description, str):
            raise TypeError('Image title and description must be text')
        title = ' '.join(title.split())
        description = ' '.join(description.split())
        if not 1 <= len(title) <= 300 or len(description) > 2000:
            raise ValueError('Invalid bounded image title or description')
        # This is an explicit operator-held reference, not a license grant.
        # No user-facing result contains the value. Block query strings,
        # email-style strings and whitespace that might carry credentials.
        if (not isinstance(rights_evidence, str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}', rights_evidence)):
            raise ValueError('Operator rights-evidence reference required')
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        return media_url, page_url, title, description, rights_evidence, now

    def add_images(self, images: list[tuple[str, str, str, str, str]]) -> int:
        """Atomically add explicitly operator-approved image metadata only."""
        if (not isinstance(images, list) or not 1 <= len(images) <= 100
                or any(not isinstance(item, (tuple, list)) or len(item) != 5
                       for item in images)):
            raise ValueError('Image batch must contain 1 to 100 valid records')
        prepared = [self._prepare_image(*item) for item in images]
        with self.connection:
            self.connection.executemany('''
              INSERT INTO images(media_url,page_url,title,description,rights_evidence,indexed_at)
              VALUES(?,?,?,?,?,?)
              ON CONFLICT(media_url) DO UPDATE SET page_url=excluded.page_url,
                title=excluded.title,description=excluded.description,
                rights_evidence=excluded.rights_evidence,indexed_at=excluded.indexed_at
            ''', prepared)
        return len(prepared)

    def add_image(self, *, page_url: str, media_url: str, title: str,
                  description: str = '', rights_evidence: str) -> None:
        self.add_images([(page_url, media_url, title, description, rights_evidence)])

    def remove_image(self, media_url: str) -> bool:
        """Immediately remove a takedown and its searchable FTS metadata."""
        with self.connection:
            cursor = self.connection.execute('DELETE FROM images WHERE media_url=?', (media_url,))
        return cursor.rowcount > 0

    def count_images(self) -> int:
        return self.connection.execute('SELECT COUNT(*) FROM images').fetchone()[0]

    def search_images(self, query: object, *, limit: int = 10) -> list[ImageHit]:
        terms = clean_query(query)
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError('Image result limit must be from 1 to 20')
        # The first pass preserves exact all-term FTS5 semantics. In a small
        # owner-approved image corpus a perfectly reasonable extra query term
        # can otherwise make the *entire* image category appear empty. Only
        # after exact results are exhausted may bounded, deterministic
        # partial-term matches fill unused slots. Never invent cards or fetch
        # a remote source to make a result count look healthier.
        distinct_terms = tuple(dict.fromkeys(terms))

        def find(query_text: str, max_rows: int) -> list[sqlite3.Row]:
            return self.connection.execute('''
          SELECT i.page_url,i.media_url,i.title,i.description,
                 i.rights_evidence,i.indexed_at,
                 bm25(images_fts,5.0,1.0) AS relevance
          FROM images_fts JOIN images AS i ON i.id=images_fts.rowid
          WHERE images_fts MATCH ? ORDER BY relevance ASC,i.media_url ASC LIMIT ?
            ''', (query_text, max_rows)).fetchall()

        exact = ' AND '.join('"' + term.replace('"', '""') + '"' for term in terms)
        rows = find(exact, limit)
        if len(rows) < limit and len(distinct_terms) > 1:
            # Match whole indexed terms under the same Unicode/diacritic
            # expectations as unicode61, not substring/title-spam counts.
            def folded(words: str) -> set[str]:
                return {
                    ''.join(c for c in unicodedata.normalize('NFD', token.casefold())
                            if not unicodedata.combining(c))
                    for token in re.findall(r'[^\W_]+', words, re.UNICODE)
                }

            target = folded(' '.join(distinct_terms))
            min_overlap = (len(target) + 1) // 2
            broad = ' OR '.join('"' + term.replace('"', '""') + '"'
                                for term in distinct_terms)
            seen = {row['media_url'] for row in rows}
            supplements = []
            # A fixed upper bound protects local CPU and memory even when a
            # common term appears in a very large owner-controlled index.
            for row in find(broad, 200):
                if row['media_url'] in seen:
                    continue
                coverage = len(target & folded(row['title'] + ' ' + row['description']))
                if coverage < min_overlap:
                    continue
                supplements.append((-coverage, row['relevance'], row['media_url'], row))
            supplements.sort(key=lambda entry: entry[:3])
            rows.extend(entry[3] for entry in supplements[:limit - len(rows)])
        return [ImageHit(
            page_url=r['page_url'], media_url=r['media_url'], title=r['title'],
            description=r['description'], rights_evidence=r['rights_evidence'],
            indexed_at=r['indexed_at'], score=round(float(-r['relevance']), 6),
        ) for r in rows]
