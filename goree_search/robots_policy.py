"""Additional fail-closed robots.txt preflight for curated HTTPS crawl commands.

Scrapy's own robots middleware remains enabled. This preflight prevents
fetching content when robots rules cannot be retrieved or interpreted.
"""
from __future__ import annotations

import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from .frontier import _https_url

USER_AGENT = "GoreeCloudSearchBot/0.1 (+https://github.com/GoreeCloud/search)"
ROBOTS_LIMIT = 512 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def robots_decision(
    url: str, proxy_url: str, *, opener=None
) -> bool | None:
    """True = allowed, False = forbidden, None = unknown / retry later.

    A 404/410 robots file is treated as absent. Other errors fail closed.
    All network fetches use the same localhost IP-pinned proxy as the crawler.
    """
    canonical = _https_url(url)
    if not proxy_url.startswith("http://127.0.0.1:"):
        raise ValueError("A trusted loopback proxy is required")
    target = urlsplit(canonical)
    robots_url = f"https://{target.netloc}/robots.txt"
    if opener is None:
        opener = build_opener(ProxyHandler({"https": proxy_url}), _NoRedirect())
    request = Request(robots_url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
    try:
        with opener.open(request, timeout=12) as response:
            if response.status != 200:
                return None
            body = response.read(ROBOTS_LIMIT + 1)
    except HTTPError as exc:
        if exc.code in (404, 410):
            return True
        if exc.code in (401, 403):
            return False
        return None
    except (URLError, TimeoutError, OSError, socket.timeout, ValueError):
        return None
    if len(body) > ROBOTS_LIMIT:
        return None
    text = body.decode("utf-8-sig", errors="replace")
    parser = RobotFileParser()
    parser.parse(text.splitlines())
    try:
        return bool(parser.can_fetch("GoreeCloudSearchBot", canonical))
    except (ValueError, TypeError):
        return None
