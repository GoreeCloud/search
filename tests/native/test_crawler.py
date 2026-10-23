# SPDX-License-Identifier: AGPL-3.0-or-later
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native_search.crawler import (CrawlPlan, Crawler, FetchResult, PinnedHttpsFetcher,
                                   canonical_url)
from native_search.index import SearchIndex


class FixtureFetcher:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        return self.responses[url]


def response(body, *, status=200, content_type='text/html', robots_tag=''):
    return FetchResult(status, content_type, body.encode(), robots_tag)


class CrawlerTests(unittest.TestCase):
    host = frozenset({'example.org'})

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = SearchIndex(Path(self.directory.name) / 'index.sqlite')

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_bounded_crawl_respects_robots_and_noindex(self):
        fetcher = FixtureFetcher({
            'https://example.org/robots.txt': response('User-agent: *\nDisallow: /blocked\nCrawl-delay: 1', content_type='text/plain'),
            'https://example.org/': response('<title>Native indexing</title><p>Independent native search index</p>'
                                             '<a href="/allowed">More</a><a href="/blocked">No</a>'
                                             '<a href="https://elsewhere.org/secret">External</a>'),
            'https://example.org/allowed': response('<title>More pages</title><p>Native discovery works</p>'),
        })
        plan = CrawlPlan(self.host, max_pages=3, max_depth=1)
        result = Crawler(self.store, plan, fetcher=fetcher, sleeper=lambda _: None).crawl(['https://example.org/'])
        self.assertEqual({'fetched': 2, 'indexed': 2, 'robots_denied': 1}, result)
        self.assertEqual(2, self.store.count())
        self.assertNotIn('https://elsewhere.org/secret', fetcher.calls)
        self.assertNotIn('https://example.org/blocked', fetcher.calls)
        self.assertEqual(2, len(self.store.search('native')))

    def test_robots_request_is_counted_for_initial_politeness_delay(self):
        requests = FixtureFetcher({
            'https://example.org/robots.txt': response(
                'User-agent: *\nAllow: /\nCrawl-delay: 2', content_type='text/plain'),
            'https://example.org/': response('<title>Example</title><p>One indexed page</p>'),
        })
        waits = []
        plan = CrawlPlan(self.host, max_pages=1, max_depth=0)
        result = Crawler(self.store, plan, fetcher=requests, sleeper=waits.append).crawl(
            ['https://example.org/'])
        self.assertEqual(1, result['indexed'])
        self.assertTrue(waits)
        self.assertGreater(waits[0], 1.5)
        self.assertLessEqual(waits[0], 2.0)

    def test_noindex_nofollow_and_meta_excluded(self):
        fetcher = FixtureFetcher({
            'https://example.org/robots.txt': response('User-agent: *\nAllow: /', content_type='text/plain'),
            'https://example.org/': response('<title>Secret</title><meta name="robots" content="noindex,nofollow">'
                                             '<p>Do not index me</p><a href="/child">Child</a>'),
        })
        got = Crawler(self.store, CrawlPlan(self.host), fetcher=fetcher).crawl(['https://example.org/'])
        self.assertEqual(0, got['indexed'])
        self.assertEqual(0, self.store.count())
        self.assertEqual(2, len(fetcher.calls))

    def test_fail_closed_when_robots_absent_or_unreachable(self):
        for status in (404, 503):
            with self.subTest(status=status):
                fetcher = FixtureFetcher({'https://example.org/robots.txt': response('',status=status)})
                with self.assertRaises(ValueError):
                    Crawler(self.store, CrawlPlan(self.host), fetcher=fetcher).crawl(['https://example.org/'])
                self.assertEqual(0, self.store.count())

    def test_response_robots_tag_prevents_indexing(self):
        fetcher = FixtureFetcher({
            'https://example.org/robots.txt': response('User-agent: *\nAllow: /', content_type='text/plain'),
            'https://example.org/': response('<title>Private</title><p>Hidden page</p>', robots_tag='noindex'),
        })
        result = Crawler(self.store, CrawlPlan(self.host), fetcher=fetcher).crawl(['https://example.org/'])
        self.assertEqual(0, result['indexed'])

    def test_redirects_are_not_followed_by_crawler(self):
        fetcher = FixtureFetcher({
            'https://example.org/robots.txt': response('User-agent: *\nAllow: /', content_type='text/plain'),
            'https://example.org/': response('Location: https://untrusted.org/', status=302),
        })
        result = Crawler(self.store, CrawlPlan(self.host), fetcher=fetcher).crawl(['https://example.org/'])
        self.assertEqual(0, result['indexed'])
        self.assertEqual(2, len(fetcher.calls))

    def test_invalid_robots_content_type_fails_closed(self):
        fetcher = FixtureFetcher({'https://example.org/robots.txt': response(
            '<html>Not a robots file</html>', content_type='text/html')})
        with self.assertRaisesRegex(ValueError, 'robots.txt'):
            Crawler(self.store, CrawlPlan(self.host), fetcher=fetcher).crawl(['https://example.org/'])
        self.assertEqual(0, self.store.count())

    def test_url_boundary_blocks_redirects_private_hosts_and_credentials(self):
        for url in ('http://example.org/', 'https://127.0.0.1/', 'https://example.org?q=sensitive',
                    'https://user:pass@example.org/', 'https://other.org/',
                    'https://example.org/%2F?x=1', 'https://example.org:444/'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_url(url, self.host)
        self.assertEqual('https://example.org/a', canonical_url('https://example.org/a#fragment', self.host))

    def test_dns_pinning_rejects_nonpublic_addresses_before_connect(self):
        mock_addr = [(2, 1, 6, '', ('127.0.0.1', 443))]
        with patch('native_search.crawler.socket.getaddrinfo', return_value=mock_addr):
            with self.assertRaisesRegex(ValueError, 'non-public'):
                PinnedHttpsFetcher(self.host).fetch('https://example.org/')

    def test_crawl_requires_finite_plan(self):
        for count in (0, 101):
            with self.assertRaises(ValueError):
                CrawlPlan(self.host, max_pages=count)
        with self.assertRaises(ValueError):
            CrawlPlan(frozenset())


if __name__ == '__main__':
    unittest.main()
