"""Allowlisted public-web Scrapy spider with robots, bounded traversal and indexing."""
from __future__ import annotations

import logging

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.exceptions import IgnoreRequest

from .extraction import excludes_index, extract_document
from .frontier import Frontier
from .indexing import ensure_index, index_document, make_client
from .security import hostname, normalize_url, public_host

logger = logging.getLogger(__name__)


class SafeNetworkMiddleware:
    """Validate every outbound request, including redirects and robots fetches."""

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        try:
            public_host(request.url, allowed_hosts=set(spider.allowed_domains), resolve=True)
        except ValueError as exc:
            raise IgnoreRequest("Public destination policy rejected request") from exc
        return None


class IndexPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        self.client = make_client()
        ensure_index(self.client)

    def process_item(self, item, spider):
        try:
            index_document(self.client, item)
        except Exception:
            if spider.frontier:
                spider.frontier.fail(item["url"], "index write failed")
            raise
        if spider.frontier:
            spider.frontier.finish(item["url"])
        return item


class WebSpider(scrapy.Spider):
    name = "goree_web"

    def __init__(self, urls: list[str], frontier: Frontier | None = None, **kwargs):
        super().__init__(**kwargs)
        self.urls = [normalize_url(url) for url in urls]
        self.allowed_domains = sorted({hostname(url) for url in self.urls})
        self.frontier = frontier

    async def start(self):
        for url in self.urls:
            yield scrapy.Request(url, callback=self.parse, errback=self.on_error)

    def on_error(self, failure):
        request = failure.request
        if self.frontier:
            self.frontier.fail(request.url)
        logger.warning("Fetch failed for host %s", hostname(request.url))

    def parse(self, response):
        url = normalize_url(response.url)
        if response.status != 200 or "text/html" not in response.headers.get(
            "Content-Type", b"").decode("latin-1").lower():
            if self.frontier:
                self.frontier.finish(url, excluded=True)
            return
        meta = response.css("meta[name='robots']::attr(content)").getall()
        x_robots = response.headers.get("X-Robots-Tag", b"").decode("latin-1")
        if excludes_index(meta, x_robots):
            if self.frontier:
                self.frontier.finish(url, excluded=True)
        else:
            title = response.css("title::text").get() or ""
            description = response.css(
                "meta[name='description']::attr(content)"
            ).get() or ""
            item = extract_document(response.text, url, title, description)
            if item:
                yield item
            elif self.frontier:
                self.frontier.finish(url, excluded=True)
        for href in response.css("a[href]::attr(href)").getall():
            try:
                target = normalize_url(response.urljoin(href))
            except ValueError:
                continue
            if hostname(target) not in self.allowed_domains:
                continue
            if self.frontier:
                self.frontier.enqueue([target])
            yield response.follow(target, callback=self.parse, errback=self.on_error)


def crawl(urls: list[str], frontier: Frontier | None = None, max_pages: int = 200) -> None:
    if not urls:
        raise ValueError("No URLs available to crawl")
    if not 1 <= max_pages <= 10000:
        raise ValueError("max_pages out of range")
    process = CrawlerProcess({
        "BOT_NAME": "GoreeCloudSearch",
        "USER_AGENT": "GoreeCloudSearchBot/0.1 (+https://github.com/GoreeCloud/search)",
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RANDOMIZE_DOWNLOAD_DELAY": False,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 15,
        "DOWNLOAD_MAXSIZE": 2 * 1024 * 1024,
        "REDIRECT_MAX_TIMES": 3,
        "RETRY_TIMES": 2,
        "DEPTH_LIMIT": 2,
        "CLOSESPIDER_PAGECOUNT": max_pages,
        "COOKIES_ENABLED": False,
        "TELNETCONSOLE_ENABLED": False,
        "DOWNLOADER_MIDDLEWARES": {"goree_search.crawler.SafeNetworkMiddleware": 90},
        "ITEM_PIPELINES": {"goree_search.crawler.IndexPipeline": 300},
        "LOG_LEVEL": "INFO",
    })
    process.crawl(WebSpider, urls=urls, frontier=frontier)
    process.start()
