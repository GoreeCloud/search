"""Durable crawl frontier with per-host leased claims and permanent operator exclusions.

A host row is locked before leasing any page from that host. All instances using
the same PostgreSQL database therefore respect one host's minimum delay.
"""
from __future__ import annotations

import os
from typing import Iterable
from urllib.parse import urlsplit

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
CREATE TABLE IF NOT EXISTS crawl_host_limits (
    host TEXT PRIMARY KEY,
    next_allowed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS crawl_exclusions (
    url TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    excluded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS crawl_frontier_due ON crawl_frontier
    (host, next_fetch_at, priority DESC)
    WHERE status IN ('queued','leased','fetched');
INSERT INTO crawl_host_limits(host)
SELECT DISTINCT host FROM crawl_frontier ON CONFLICT DO NOTHING;
"""


def _https_url(url: str) -> str:
    normalized = normalize_url(url)
    if urlsplit(normalized).scheme != "https":
        raise ValueError("This alpha crawler only accepts HTTPS URLs")
    return normalized


class Frontier:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get("DATABASE_URL", "")
        if not self.dsn:
            raise RuntimeError("DATABASE_URL required for crawl frontier")

    def init(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(SCHEMA, prepare=False)

    def enqueue(self, urls: Iterable[str], priority: int = 0) -> int:
        if not -10 <= priority <= 10:
            raise ValueError("Priority must be in -10..10")
        rows = list(dict.fromkeys(_https_url(url) for url in urls))
        if not rows:
            return 0
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO crawl_host_limits(host) VALUES (%s) ON CONFLICT DO NOTHING",
                    [(hostname(url),) for url in rows],
                )
                count = 0
                for url in rows:
                    cur.execute(
                        """
                        INSERT INTO crawl_frontier(url, host, priority)
                        SELECT %s, %s, %s
                        WHERE NOT EXISTS (
                          SELECT 1 FROM crawl_exclusions WHERE url=%s
                        )
                        ON CONFLICT (url) DO NOTHING
                        RETURNING url
                        """,
                        (url, hostname(url), priority, url),
                    )
                    count += int(cur.fetchone() is not None)
        return count

    def claim(self, limit: int = 20, delay_seconds: int = 5) -> list[str]:
        """Lease at most one due URL per host and atomically delay that host.

        A transaction takes row locks on host limits with SKIP LOCKED. Another
        worker cannot simultaneously claim a different URL from the same host.
        """
        if not 1 <= limit <= 200 or not 1 <= delay_seconds <= 3600:
            raise ValueError("Invalid claim limit or host delay")
        claimed: list[str] = []
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT h.host
                    FROM crawl_host_limits AS h
                    WHERE h.next_allowed_at <= now()
                      AND EXISTS (
                        SELECT 1 FROM crawl_frontier AS f
                        WHERE f.host = h.host
                          AND f.attempts < 4
                          AND NOT EXISTS (
                            SELECT 1 FROM crawl_exclusions AS e WHERE e.url=f.url
                          )
                          AND (
                            (f.status IN ('queued','fetched') AND f.next_fetch_at <= now())
                            OR (f.status='leased' AND f.lease_until <= now())
                          )
                      )
                    ORDER BY h.next_allowed_at, h.host
                    FOR UPDATE OF h SKIP LOCKED LIMIT %s
                    """,
                    (limit,),
                )
                for (host,) in cur.fetchall():
                    cur.execute(
                        """
                        WITH due AS (
                          SELECT url FROM crawl_frontier AS f
                          WHERE host=%s AND attempts < 4
                            AND NOT EXISTS (
                              SELECT 1 FROM crawl_exclusions AS e WHERE e.url=f.url
                            )
                            AND (
                              (status IN ('queued','fetched') AND next_fetch_at <= now())
                              OR (status='leased' AND lease_until <= now())
                            )
                          ORDER BY priority DESC, next_fetch_at, url
                          FOR UPDATE SKIP LOCKED LIMIT 1
                        )
                        UPDATE crawl_frontier AS f
                        SET status='leased',
                            lease_until=now()+interval '20 minutes',
                            attempts=CASE WHEN f.status='fetched' THEN 1
                                          ELSE f.attempts + 1 END
                        FROM due WHERE f.url=due.url RETURNING f.url
                        """,
                        (host,),
                    )
                    result = cur.fetchone()
                    if result is None:
                        continue
                    claimed.append(result[0])
                    cur.execute(
                        """
                        UPDATE crawl_host_limits
                        SET next_allowed_at=now()+make_interval(secs => %s)
                        WHERE host=%s
                        """,
                        (delay_seconds, host),
                    )
        return claimed

    def is_excluded(self, url: str) -> bool:
        canonical = _https_url(url)
        with psycopg.connect(self.dsn) as conn:
            return conn.execute(
                "SELECT 1 FROM crawl_exclusions WHERE url=%s", (canonical,)
            ).fetchone() is not None

    def exclude_url(self, url: str, reason: str) -> None:
        """Operator decision to block re-ingestion; index deletion is separate.

        For guaranteed final absence, stop workers, exclude, purge index and
        verify against the search service before restarting workers.
        """
        canonical = _https_url(url)
        reason = reason.strip()
        if not 3 <= len(reason) <= 300:
            raise ValueError("Reason must have 3 to 300 characters")
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                INSERT INTO crawl_exclusions(url,reason) VALUES(%s,%s)
                ON CONFLICT(url) DO UPDATE
                SET reason=EXCLUDED.reason, excluded_at=now()
                """,
                (canonical, reason),
            )
            conn.execute(
                """
                UPDATE crawl_frontier
                SET status='excluded', lease_until=NULL, last_error=NULL
                WHERE url=%s
                """,
                (canonical,),
            )

    def finish(self, url: str, *, excluded: bool = False, recrawl_days: int = 7) -> None:
        if not 1 <= recrawl_days <= 365:
            raise ValueError("recrawl_days must be 1 to 365")
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                UPDATE crawl_frontier AS f
                SET status=%s, lease_until=NULL, last_error=NULL,
                    last_fetched_at=now(),
                    next_fetch_at=now()+make_interval(days => %s)
                WHERE url=%s AND NOT EXISTS (
                  SELECT 1 FROM crawl_exclusions AS e WHERE e.url=f.url
                )
                """,
                ("excluded" if excluded else "fetched", recrawl_days, _https_url(url)),
            )

    def fail(self, url: str, detail: str = "fetch failed") -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                UPDATE crawl_frontier AS f
                SET status=CASE WHEN attempts >= 4 THEN 'failed' ELSE 'queued' END,
                    next_fetch_at=now() + make_interval(secs =>
                        LEAST(86400, 60 * power(2, LEAST(attempts, 10)))::int),
                    lease_until=NULL, last_error=%s
                WHERE url=%s AND NOT EXISTS (
                  SELECT 1 FROM crawl_exclusions AS e WHERE e.url=f.url
                )
                """,
                (detail[:180], _https_url(url)),
            )
