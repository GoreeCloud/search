# SPDX-License-Identifier: AGPL-3.0-or-later
"""Explicit-seed HTTPS crawler with pinned public IPs and fail-closed robots rules.

No crawling occurs on import. Network access requires a separate CLI switch,
explicit allowed public hostnames, and explicit seed URLs.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from html.parser import HTMLParser
from http.client import HTTPSConnection
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from .index import SearchIndex

USER_AGENT = 'GoreeCloudSearchCrawler/0.1 (+https://github.com/GoreeCloud/search)'
MAX_DOWNLOAD = 512_000


def canonical_url(raw: str, allowed_hosts: frozenset[str]) -> str:
    if not isinstance(raw, str) or not raw or raw != raw.strip():
        raise ValueError('Invalid URL')
    if any(ord(c) <= 32 or ord(c) == 127 or c == '\\' for c in raw):
        raise ValueError('Unsafe URL encoding')
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname
        if (parsed.scheme != 'https' or not host or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.query or parsed.netloc.endswith('.')
                or '%' in parsed.netloc or host.lower() not in allowed_hosts):
            raise ValueError('URL outside explicit HTTPS crawl allowlist')
    except ValueError as exc:
        raise ValueError('Invalid crawl URL or HTTPS authority') from exc
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass  # Public hostnames are permitted; actual DNS is checked at fetch.
    else:
        raise ValueError('IP literal hosts are not crawlable')
    if parsed.fragment:
        parsed = parsed._replace(fragment='')
    path = parsed.path or '/'
    if '/..' in path or '/./' in path:
        raise ValueError('Ambiguous URL path')
    return urlunsplit(('https', host.lower(), path, '', ''))


@dataclass(frozen=True)
class FetchResult:
    status: int
    content_type: str
    body: bytes
    robots_tag: str = ''


class PinnedHttpsFetcher:
    """Resolve once, reject private addresses, then pin TLS socket to checked IP."""

    def fetch(self, url: str) -> FetchResult:
        parsed = urlsplit(url)
        assert parsed.scheme == 'https' and parsed.hostname
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        verified: list[str] = []
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError('DNS resolved to a non-public address')
            verified.append(str(ip))
        if not verified:
            raise ValueError('DNS resolution returned no public addresses')
        conn = HTTPSConnection(parsed.hostname, timeout=8, context=ssl.create_default_context())
        try:
            # Bypass a second hostname resolution; retain the original SNI and
            # certificate hostname check on the TLS socket.
            conn.sock = ssl.create_default_context().wrap_socket(
                socket.create_connection((verified[0], 443), timeout=8),
                server_hostname=parsed.hostname,
            )
            conn.request('GET', parsed.path or '/', headers={
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,text/plain;q=0.5',
                'Accept-Encoding': 'identity',
                'Connection': 'close',
            })
            response = conn.getresponse()
            data = response.read(MAX_DOWNLOAD + 1)
            if len(data) > MAX_DOWNLOAD:
                raise ValueError('Response exceeds crawl byte budget')
            return FetchResult(status=response.status,
                               content_type=response.getheader('Content-Type', ''),
                               body=data, robots_tag=response.getheader('X-Robots-Tag', ''))
        finally:
            conn.close()


class PageExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.links: list[str] = []
        self.title_depth = 0
        self.skip_depth = 0
        self.noindex = False
        self.nofollow = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in ('script', 'style', 'noscript', 'svg'):
            self.skip_depth += 1
        if tag == 'title':
            self.title_depth += 1
        if tag == 'meta' and values.get('name', '').lower() in ('robots', 'goreecloudsearchcrawler'):
            directives = values.get('content', '').lower().split(',')
            self.noindex |= any(x.strip() in ('noindex', 'none') for x in directives)
            self.nofollow |= any(x.strip() in ('nofollow', 'none') for x in directives)
        if tag == 'a' and values.get('href') and 'nofollow' not in values.get('rel', '').lower().split():
            self.links.append(values['href'])

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'svg'):
            self.skip_depth = max(self.skip_depth - 1, 0)
        if tag == 'title':
            self.title_depth = max(self.title_depth - 1, 0)

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.title_depth:
            self.title_parts.append(data)
        elif data.strip():
            self.body_parts.append(data)


@dataclass(frozen=True)
class CrawlPlan:
    allowed_hosts: frozenset[str]
    max_pages: int = 10
    max_depth: int = 1
    min_interval_seconds: float = 1.0

    def __post_init__(self):
        if (not self.allowed_hosts or any(not name or name != name.lower() or ':' in name
                or '/' in name or name.endswith('.') for name in self.allowed_hosts)
                or not 1 <= self.max_pages <= 100 or not 0 <= self.max_depth <= 3
                or not 1 <= self.min_interval_seconds <= 60):
            raise ValueError('Invalid explicit crawl limits or hostname allowlist')


class Crawler:
    def __init__(self, index: SearchIndex, plan: CrawlPlan, fetcher=None, sleeper=time.sleep):
        self.index = index
        self.plan = plan
        self.fetcher = fetcher if fetcher is not None else PinnedHttpsFetcher()
        self.sleeper = sleeper
        self.robots: dict[str, RobotFileParser] = {}
        self.last_request: dict[str, float] = {}

    def _robots(self, host: str) -> RobotFileParser:
        if host not in self.robots:
            response = self.fetcher.fetch('https://' + host + '/robots.txt')
            if (response.status != 200 or len(response.body) > 128_000
                    or 'text/plain' not in response.content_type.lower()):
                raise ValueError('Cannot verify text/plain robots.txt; refusing to crawl')
            policy = RobotFileParser()
            policy.parse(response.body.decode('utf-8', errors='replace').splitlines())
            # robots.txt is itself a host request: apply politeness before the
            # first HTML fetch, not just between later HTML pages.
            self.last_request[host] = time.monotonic()
            self.robots[host] = policy
        return self.robots[host]

    def crawl(self, seeds: list[str]) -> dict[str, int]:
        queue: deque[tuple[str, int]] = deque()
        for seed in seeds:
            queue.append((canonical_url(seed, self.plan.allowed_hosts), 0))
        if not queue or len(queue) > 100:
            raise ValueError('Provide 1 to 100 explicit seeds')
        seen: set[str] = set()
        scanned = saved = denied = 0
        while queue and scanned < self.plan.max_pages:
            raw, depth = queue.popleft()
            url = canonical_url(raw, self.plan.allowed_hosts)
            if url in seen:
                continue
            seen.add(url)
            host = urlsplit(url).hostname
            policy = self._robots(host)
            if not policy.can_fetch(USER_AGENT, url):
                denied += 1
                continue
            interval = max(self.plan.min_interval_seconds, float(policy.crawl_delay(USER_AGENT) or 0))
            if host in self.last_request:
                elapsed = time.monotonic() - self.last_request[host]
                if elapsed < interval:
                    self.sleeper(interval - elapsed)
            self.last_request[host] = time.monotonic()
            response = self.fetcher.fetch(url)
            scanned += 1
            if response.status != 200 or 'text/html' not in response.content_type.lower():
                continue  # No redirects, non-HTML data or errors indexed.
            page = PageExtractor()
            page.feed(response.body.decode('utf-8', errors='replace'))
            directives = response.robots_tag.lower()
            if page.noindex or 'noindex' in directives or 'none' in directives:
                continue
            title = ' '.join(''.join(page.title_parts).split())
            body = ' '.join(' '.join(page.body_parts).split())
            if title and body:
                self.index.add(url=url, title=title, body=body)
                saved += 1
            if depth < self.plan.max_depth and not page.nofollow and 'nofollow' not in directives:
                for link in page.links[:50]:
                    if len(queue) >= 100:
                        break
                    try:
                        next_url = canonical_url(urljoin(url, link), self.plan.allowed_hosts)
                    except (ValueError, TypeError):
                        continue
                    if next_url not in seen:
                        queue.append((next_url, depth + 1))
        return {'fetched': scanned, 'indexed': saved, 'robots_denied': denied}
