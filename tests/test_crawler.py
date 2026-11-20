from unittest.mock import MagicMock

import pytest
import scrapy
from scrapy.http import HtmlResponse, Request

from goree_search.crawler import IndexPipeline, SafeNetworkMiddleware, WebSpider


def response_for(html: str, *, headers=None, status=200) -> HtmlResponse:
    request = Request(
        "https://example.org/seed", meta={"frontier_url": "https://example.org/seed"}
    )
    return HtmlResponse(
        url=request.url, body=html.encode(), encoding="utf-8", request=request,
        headers=headers or {b"Content-Type": b"text/html; charset=utf-8"},
        status=status,
    )


def test_spider_queues_links_without_fetching_immediately():
    frontier = MagicMock()
    spider = WebSpider(["https://example.org/seed"], frontier=frontier)
    html = (
        "<html><head><title>My page</title></head><body>"
        "<article><p>" +
        "Public web search is useful when we control how content is indexed. " * 6 +
        "</p></article><a href='/next'>Next</a></body></html>"
    )
    outputs = list(spider.parse(response_for(html)))
    docs = [x for x in outputs if isinstance(x, dict)]
    assert len(docs) == 1
    assert docs[0]["_frontier_url"] == "https://example.org/seed"
    assert not any(isinstance(x, scrapy.Request) for x in outputs)
    frontier.enqueue.assert_called_once_with(["https://example.org/next"])


def test_nofollow_prevents_discovery():
    frontier = MagicMock()
    spider = WebSpider(["https://example.org/seed"], frontier=frontier)
    html = (
        '<html><head><meta name="robots" content="nofollow"></head>'
        '<body><a href="/next">Next</a></body></html>'
    )
    list(spider.parse(response_for(html)))
    frontier.enqueue.assert_not_called()


def test_noindex_tombstones_old_document():
    frontier = MagicMock()
    spider = WebSpider(["https://example.org/seed"], frontier=frontier)
    html = (
        '<html><head><meta name="robots" content="noindex"></head>'
        '<body><article>Deleted from results</article></body></html>'
    )
    docs = list(spider.parse(response_for(html)))
    assert docs == [{
        "url": "https://example.org/seed",
        "_delete": True,
        "_frontier_url": "https://example.org/seed",
    }]


def test_http_404_tombstones_old_document():
    spider = WebSpider(["https://example.org/seed"])
    docs = list(spider.parse(response_for("<html></html>", status=404)))
    assert docs[0]["_delete"] is True


def test_index_pipeline_respects_operator_exclusions():
    pipeline = IndexPipeline()
    pipeline.client = MagicMock()
    spider = WebSpider(["https://example.org/seed"], frontier=MagicMock())
    spider.frontier.is_excluded.return_value = True
    item = {"url": "https://example.org/seed", "_frontier_url": "https://example.org/seed"}
    pipeline.process_item(item, spider)
    pipeline.client.delete.assert_called_once()
    pipeline.client.index.assert_not_called()


def test_middleware_rejects_unapproved_host():
    spider = WebSpider(["https://example.org/seed"])
    middleware = SafeNetworkMiddleware("http://127.0.0.1:8081")
    with pytest.raises(scrapy.exceptions.IgnoreRequest):
        middleware.process_request(Request("https://other.org/"), spider)


def test_middleware_sets_loopback_proxy():
    spider = WebSpider(["https://example.org/seed"])
    middleware = SafeNetworkMiddleware("http://127.0.0.1:8081")
    request = Request("https://example.org/robots.txt")
    assert middleware.process_request(request, spider) is None
    assert request.meta["proxy"] == "http://127.0.0.1:8081"


def test_middleware_fails_closed_without_proxy():
    spider = WebSpider(["https://example.org/seed"])
    with pytest.raises(scrapy.exceptions.IgnoreRequest):
        SafeNetworkMiddleware("").process_request(
            Request("https://example.org/robots.txt"), spider
        )


from contextlib import nullcontext
from goree_search.crawler import crawl


def test_robots_unknown_prevents_any_page_fetch(monkeypatch):
    frontier = MagicMock()
    monkeypatch.setattr(
        "goree_search.crawler.local_https_proxy",
        lambda hosts: nullcontext("http://127.0.0.1:12345"),
    )
    monkeypatch.setattr("goree_search.crawler.robots_decision", lambda url, proxy: None)
    with pytest.raises(ValueError, match="robots preflight"):
        crawl(["https://example.org/seed"], frontier=frontier)
    frontier.fail.assert_called_once_with(
        "https://example.org/seed", "robots policy unavailable"
    )


def test_robots_forbidden_excludes_and_purges_old_index(monkeypatch):
    frontier = MagicMock()
    delete = MagicMock()
    monkeypatch.setattr(
        "goree_search.crawler.local_https_proxy",
        lambda hosts: nullcontext("http://127.0.0.1:12345"),
    )
    monkeypatch.setattr("goree_search.crawler.robots_decision", lambda url, proxy: False)
    monkeypatch.setattr("goree_search.crawler.make_client", MagicMock())
    monkeypatch.setattr("goree_search.crawler.delete_document", delete)
    with pytest.raises(ValueError, match="robots preflight"):
        crawl(["https://example.org/seed"], frontier=frontier)
    frontier.finish.assert_called_once_with("https://example.org/seed", excluded=True)
    delete.assert_called_once()


def test_robots_allowed_then_crawler_starts(monkeypatch):
    instance = MagicMock()
    factory = MagicMock(return_value=instance)
    monkeypatch.setattr(
        "goree_search.crawler.local_https_proxy",
        lambda hosts: nullcontext("http://127.0.0.1:12345"),
    )
    monkeypatch.setattr("goree_search.crawler.robots_decision", lambda url, proxy: True)
    monkeypatch.setattr("goree_search.crawler.CrawlerProcess", factory)
    crawl(["https://example.org/seed"], max_pages=2)
    instance.crawl.assert_called_once()
    assert instance.crawl.call_args.kwargs["urls"] == ["https://example.org/seed"]
    instance.start.assert_called_once()
