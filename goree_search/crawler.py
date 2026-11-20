"""Curated HTTPS crawler with durable discovery, scoped proxy, robots and purging."""
from __future__ import annotations

import logging

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.exceptions import IgnoreRequest

from .egress_proxy import local_https_proxy
from .extraction import excludes_index, extract_document
from .frontier import Frontier, _https_url
from .indexing import delete_document, ensure_index, index_document, make_client
from .robots_policy import USER_AGENT, robots_decision
from .security import hostname, public_host

logger = logging.getLogger(__name__)


class SafeNetworkMiddleware:
    """Every crawler download (also robots.txt) must use the pinned-IP proxy."""

    def __init__(self, proxy_url: str):
        self.proxy_url = proxy_url

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.get("GORE_SEARCH_PROXY", ""))

    def process_request(self, request, spider):
        try:
            _https_url(request.url)
            public_host(request.url, allowed_hosts=set(spider.allowed_domains), resolve=False)
            if not self.proxy_url.startswith("http://127.0.0.1:"):
                raise ValueError("Crawler proxy is not configured")
            request.meta["proxy"] = self.proxy_url
        except ValueError as exc:
            raise IgnoreRequest("Crawler destination policy rejected request") from exc
        return None


class IndexPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        self.client = make_client()
        ensure_index(self.client)

    def process_item(self, item, spider):
        source = item.get("_frontier_url", item["url"])
        try:
            if item.get("_delete") or (
                spider.frontier is not None and spider.frontier.is_excluded(item["url"])
            ):
                delete_document(self.client, item["url"])
                if spider.frontier:
                    spider.frontier.finish(source, excluded=True)
            else:
                index_document(self.client, item)
                # A concurrent operator exclusion takes precedence after ingestion.
                if spider.frontier is not None and spider.frontier.is_excluded(item["url"]):
                    delete_document(self.client, item["url"])
                if spider.frontier:
                    spider.frontier.finish(source)
        except Exception:
            if spider.frontier:
                spider.frontier.fail(source, "index operation failed")
            raise
        return item


class WebSpider(scrapy.Spider):
    name = "goree_web"

    def __init__(self, urls: list[str], frontier: Frontier | None = None, **kwargs):
        super().__init__(**kwargs)
        self.urls = [_https_url(url) for url in urls]
        self.allowed_domains = sorted({hostname(url) for url in self.urls})
        self.frontier = frontier

    async def start(self):
        for url in self.urls:
            if self.frontier is not None and self.frontier.is_excluded(url):
                continue
            yield scrapy.Request(
                url, callback=self.parse, errback=self.on_error,
                meta={"frontier_url": url},
                dont_filter=False,
            )

    def on_error(self, failure):
        request = failure.request
        if self.frontier:
            self.frontier.fail(request.meta.get("frontier_url", request.url))
        # No URL or query strings in routine logs.
        logger.warning("Crawler fetch failed for a scheduled HTTPS host")

    def parse(self, response):
        url = _https_url(response.url)
        source_url = response.meta.get("frontier_url", url)
        content_type = response.headers.get("Content-Type", b"").decode("latin-1").lower()
        if response.status != 200 or "text/html" not in content_type:
            yield {"url": url, "_delete": True, "_frontier_url": source_url}
            return

        meta = response.css("meta[name='robots']::attr(content)").getall()
        x_robots = response.headers.get("X-Robots-Tag", b"").decode("latin-1")
        if excludes_index(meta, x_robots):
            yield {"url": url, "_delete": True, "_frontier_url": source_url}
        else:
            title = response.css("title::text").get() or ""
            description = response.css("meta[name='description']::attr(content)").get() or ""
            item = extract_document(response.text, url, title, description)
            if item is not None:
                item["_frontier_url"] = source_url
                yield item
            elif self.frontier:
                self.frontier.finish(source_url, excluded=True)

        directives = ",".join(meta + [x_robots]).lower()
        if "nofollow" in directives or "none" in directives:
            return
        # Links are *queued*, never fetched directly. Every actual fetch must
        # pass through the atomic per-host PostgreSQL scheduler on a later run.
        if self.frontier is not None:
            for href in response.css("a[href]:not([rel~='nofollow'])::attr(href)").getall():
                try:
                    target = _https_url(response.urljoin(href))
                except ValueError:
                    continue
                if hostname(target) in self.allowed_domains:
                    self.frontier.enqueue([target])


def crawl(urls: list[str], frontier: Frontier | None = None, max_pages: int = 200) -> None:
    if not urls:
        raise ValueError("No URLs available to crawl")
    if not 1 <= max_pages <= 10000:
        raise ValueError("max_pages out of range")
    urls = [_https_url(url) for url in urls]
    # Fail closed against DNS rebinding: HTTPS CONNECT resolves once, checks
    # globally routable IPs and opens TCP to the validated IP, not the hostname.
    with local_https_proxy({hostname(url) for url in urls}) as proxy:
        approved = []
        for url in urls:
            decision = robots_decision(url, proxy)
            if decision is True:
                approved.append(url)
            elif frontier is not None:
                if decision is False:
                    # Explicit disallow: exclude scheduled URL and purge old hits.
                    frontier.finish(url, excluded=True)
                    delete_document(make_client(), url)
                else:
                    # Network/policy uncertainty: postpone; never fetch the page.
                    frontier.fail(url, "robots policy unavailable")
        if not approved:
            raise ValueError("No URLs passed fail-closed robots preflight")
        process = CrawlerProcess({
            "BOT_NAME": "GoreeCloudSearch",
            "USER_AGENT": USER_AGENT,
            "ROBOTSTXT_OBEY": True,
            "CONCURRENT_REQUESTS": 4,
            "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
            "DOWNLOAD_DELAY": 2.0,
            "RANDOMIZE_DOWNLOAD_DELAY": False,
            "AUTOTHROTTLE_ENABLED": True,
            "DOWNLOAD_TIMEOUT": 15,
            "DOWNLOAD_MAXSIZE": 2 * 1024 * 1024,
            "REDIRECT_ENABLED": False,
            "METAREFRESH_ENABLED": False,
            "HTTPERROR_ALLOW_ALL": True,
            "RETRY_TIMES": 2,
            "DEPTH_LIMIT": 1,
            "CLOSESPIDER_PAGECOUNT": max_pages,
            "COOKIES_ENABLED": False,
            "TELNETCONSOLE_ENABLED": False,
            "HTTPPROXY_ENABLED": True,
            "GORE_SEARCH_PROXY": proxy,
            "DOWNLOAD_HANDLERS": {"file": None, "data": None, "ftp": None},
            "DOWNLOADER_MIDDLEWARES": {"goree_search.crawler.SafeNetworkMiddleware": 90},
            "ITEM_PIPELINES": {"goree_search.crawler.IndexPipeline": 300},
            "LOG_LEVEL": "INFO",
        })
        process.crawl(WebSpider, urls=approved, frontier=frontier)
        process.start()
