"""Robots policy tests are synthetic: never make public requests."""
from io import BytesIO
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock

import pytest

from goree_search.robots_policy import ROBOTS_LIMIT, robots_decision

URL = "https://example.org/hidden/article"
PROXY = "http://127.0.0.1:38999"


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.stream = BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.stream.read(limit)


def opener_for(body):
    opener = MagicMock()
    opener.open.return_value = FakeResponse(body)
    return opener


def test_disallow_and_allow_by_robots_rules():
    forbid = opener_for(b"User-agent: GoreeCloudSearchBot\nDisallow: /hidden/\n")
    allow = opener_for(b"User-agent: *\nAllow: /\n")
    assert robots_decision(URL, PROXY, opener=forbid) is False
    assert robots_decision(URL, PROXY, opener=allow) is True
    assert forbid.open.call_args.args[0].full_url == "https://example.org/robots.txt"


@pytest.mark.parametrize("code,decision", [(404, True), (410, True), (403, False), (401, False), (500, None), (302, None)])
def test_http_status_policy(code, decision):
    opener = MagicMock()
    opener.open.side_effect = HTTPError(
        "https://example.org/robots.txt", code, "synthetic", {}, None
    )
    assert robots_decision(URL, PROXY, opener=opener) is decision


def test_failure_and_oversized_policy_fail_closed():
    opener = MagicMock()
    opener.open.side_effect = URLError("synthetic network failure")
    assert robots_decision(URL, PROXY, opener=opener) is None
    assert robots_decision(URL, PROXY, opener=opener_for(b"X" * (ROBOTS_LIMIT + 1))) is None


def test_reject_wrong_proxy_and_http_seed():
    with pytest.raises(ValueError):
        robots_decision(URL, "http://example.org:8080", opener=MagicMock())
    with pytest.raises(ValueError):
        robots_decision("http://example.org/", PROXY, opener=MagicMock())
