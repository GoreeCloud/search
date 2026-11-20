"""PostgreSQL integration tests use only a disposable TEST_DATABASE_URL."""
import os

import psycopg
import pytest

from goree_search.frontier import Frontier

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="Requires disposable PostgreSQL CI service"
)
URL1 = "https://goreecloud-frontier-fixture.org/a"
URL2 = "https://goreecloud-frontier-fixture.org/b"


@pytest.fixture
def frontier():
    f = Frontier(os.environ["TEST_DATABASE_URL"])
    f.init()
    with psycopg.connect(f.dsn) as conn:
        conn.execute("DELETE FROM crawl_exclusions WHERE url IN (%s,%s)", (URL1, URL2))
        conn.execute(
            "DELETE FROM crawl_frontier WHERE host=%s",
            ("goreecloud-frontier-fixture.org",),
        )
        conn.execute(
            "DELETE FROM crawl_host_limits WHERE host=%s",
            ("goreecloud-frontier-fixture.org",),
        )
    yield f
    with psycopg.connect(f.dsn) as conn:
        conn.execute("DELETE FROM crawl_exclusions WHERE url IN (%s,%s)", (URL1, URL2))
        conn.execute(
            "DELETE FROM crawl_frontier WHERE host=%s",
            ("goreecloud-frontier-fixture.org",),
        )
        conn.execute(
            "DELETE FROM crawl_host_limits WHERE host=%s",
            ("goreecloud-frontier-fixture.org",),
        )


def allow_next_host_claim(frontier):
    with psycopg.connect(frontier.dsn) as conn:
        conn.execute(
            "UPDATE crawl_host_limits SET next_allowed_at=now()-interval '1 second' "
            "WHERE host=%s", ("goreecloud-frontier-fixture.org",)
        )


def test_one_url_per_host_and_completion(frontier):
    assert frontier.enqueue([URL1, URL2, URL1]) == 2
    urls = frontier.claim(10, delay_seconds=60)
    assert len(urls) == 1
    assert frontier.claim(10) == []
    frontier.finish(urls[0])
    allow_next_host_claim(frontier)
    remaining = frontier.claim(10)
    assert len(remaining) == 1 and remaining[0] != urls[0]
    frontier.fail(remaining[0], "synthetic retry")
    with psycopg.connect(frontier.dsn) as conn:
        status = dict(conn.execute(
            "SELECT url, status FROM crawl_frontier WHERE host=%s",
            ("goreecloud-frontier-fixture.org",),
        ).fetchall())
    assert status[urls[0]] == "fetched"
    assert status[remaining[0]] == "queued"


def test_recrawl_and_operator_exclusion(frontier):
    frontier.enqueue([URL1])
    assert frontier.claim(1) == [URL1]
    frontier.finish(URL1, recrawl_days=1)
    allow_next_host_claim(frontier)
    assert frontier.claim(1) == []
    with psycopg.connect(frontier.dsn) as conn:
        conn.execute(
            "UPDATE crawl_frontier SET next_fetch_at=now()-interval '1 second' WHERE url=%s",
            (URL1,)
        )
    assert frontier.claim(1) == [URL1]
    frontier.exclude_url(URL1, "Verified operator removal")
    assert frontier.is_excluded(URL1)
    allow_next_host_claim(frontier)
    assert frontier.claim(1) == []
    assert frontier.enqueue([URL1]) == 0
    frontier.finish(URL1)
    with psycopg.connect(frontier.dsn) as conn:
        status = conn.execute(
            "SELECT status FROM crawl_frontier WHERE url=%s", (URL1,)
        ).fetchone()
    assert status[0] == "excluded"
