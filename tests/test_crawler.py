from unittest.mock import MagicMock

import scrapy
import pytest
from scrapy.http import HtmlResponse, Request

from goree_search.crawler import SafeNetworkMiddleware, WebSpider


def test_spider_indexes_document_and_discovery_with_frontier():
    frontier = MagicMock()
    spider = WebSpider(["https://example.org/seed"], frontier=frontier)
    html = (
        "<html><head><title>My page</title></head><body>"
        "<article><p>" + "Public web search is useful when we control how content is indexed. " * 6 + "</p></article>"
        '<a href="/next">Next</a></body></html>'
    )
    request = Request("https://example.org/seed", meta={"frontier_url": "https://example.org/seed"})
    response = HtmlResponse(url=request.url, body=html.encode(), encoding="utf-8", request=request)
    outputs = list(spider.parse(response))
    docs = [value for value in outputs if isinstance(value, dict)]
    next_requests = [value for value in outputs if isinstance(value, scrapy.Request)]
    assert len(docs) == 1
    assert docs[0]["_frontier_url"] == "https://example.org/seed"
    assert next_requests[0].meta["frontier_url"] == "https://example.org/next"
    frontier.enqueue.assert_called_once()


def test_nofollow_prevents_discovery():
    frontier = MagicMock()
    spider = WebSpider(["https://example.org/seed"], frontier=frontier)
    html = '<html><head><meta name="robots" content="nofollow"></head><body><a href="/next">Next</a></body></html>'
    request = Request("https://example.org/seed", meta={"frontier_url": "https://example.org/seed"})
    response = HtmlResponse(url=request.url, body=html.encode(), encoding="utf-8", request=request)
    assert list(spider.parse(response)) == []
    frontier.enqueue.assert_not_called()


def test_middleware_rejects_unapproved_host():
    spider = WebSpider(["https://example.org/seed"])
    middleware = SafeNetworkMiddleware()
    with pytest.raises(scrapy.exceptions.IgnoreRequest):
        middleware.process_request(Request("https://other.org/"), spider)
