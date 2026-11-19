"""Disposable PostgreSQL integration tests (only run with TEST_DATABASE_URL)."""
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
        conn.execute("DELETE FROM crawl_frontier WHERE host=%s", ("goreecloud-frontier-fixture.org",))
    yield f
    with psycopg.connect(f.dsn) as conn:
        conn.execute("DELETE FROM crawl_frontier WHERE host=%s", ("goreecloud-frontier-fixture.org",))


def test_claim_and_completion(frontier):
    frontier.enqueue([URL1, URL2, URL1])
    urls = frontier.claim(10)
    assert set(urls) == {URL1, URL2}
    assert frontier.claim(10) == []
    frontier.finish(URL1)
    frontier.fail(URL2, "synthetic retry")
    with psycopg.connect(frontier.dsn) as conn:
        status = dict(conn.execute(
            "SELECT url, status FROM crawl_frontier WHERE host=%s",
            ("goreecloud-frontier-fixture.org",),
        ).fetchall())
    assert status[URL1] == "fetched"
    assert status[URL2] == "queued"
