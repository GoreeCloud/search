"""PostgreSQL-backed crawl queue with atomic leased claims and retry scheduling."""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Iterable

import psycopg

from .security import hostname, normalize_url

SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_frontier (
    url TEXT PRIMARY KEY,
    host TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','leased','fetched','excluded','failed')),
    priority INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_fetch_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_until TIMESTAMPTZ,
    last_fetched_at TIMESTAMPTZ,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS crawl_frontier_due
    ON crawl_frontier (next_fetch_at, priority DESC)
    WHERE status IN ('queued','leased');
"""


class Frontier:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get("DATABASE_URL", "")
        if not self.dsn:
            raise RuntimeError("DATABASE_URL required for the crawl frontier")

    def init(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(SCHEMA, prepare=False)

    def enqueue(self, urls: Iterable[str], priority: int = 0) -> int:
        rows = [(normalize_url(url), hostname(url), priority) for url in urls]
        if not rows:
            return 0
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO crawl_frontier(url,host,priority) VALUES(%s,%s,%s) "
                    "ON CONFLICT(url) DO NOTHING",
                    rows,
                )
        return len(rows)

    def claim(self, limit: int = 20) -> list[str]:
        if not 1 <= limit <= 200:
            raise ValueError("claim limit must be between 1 and 200")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH claimed AS (
                        SELECT url FROM crawl_frontier
                        WHERE (status='queued' AND next_fetch_at <= now())
                           OR (status='leased' AND lease_until <= now())
                        ORDER BY priority DESC, next_fetch_at ASC
                        FOR UPDATE SKIP LOCKED LIMIT %s
                    )
                    UPDATE crawl_frontier AS f
                    SET status='leased', lease_until=now()+interval '20 minutes',
                        attempts=f.attempts+1
                    FROM claimed WHERE f.url=claimed.url RETURNING f.url
                    """,
                    (limit,),
                )
                return [row[0] for row in cur.fetchall()]

    def finish(self, url: str, *, excluded: bool = False) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE crawl_frontier SET status=%s, lease_until=NULL, "
                "last_error=NULL, last_fetched_at=now() WHERE url=%s",
                ("excluded" if excluded else "fetched", normalize_url(url)),
            )

    def fail(self, url: str, detail: str = "fetch failed") -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                UPDATE crawl_frontier
                SET status=CASE WHEN attempts >= 4 THEN 'failed' ELSE 'queued' END,
                    next_fetch_at=now() + make_interval(secs =>
                        LEAST(86400, 60 * power(2, LEAST(attempts, 10)))::int),
                    lease_until=NULL, last_error=%s
                WHERE url=%s
                """,
                (detail[:180], normalize_url(url)),
            )
