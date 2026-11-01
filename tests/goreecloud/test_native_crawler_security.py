"""Offline regressions for the native crawler's actual HTTPS fetch boundary."""
import socket
import unittest
from unittest.mock import Mock, patch

from native_search.crawler import (
    MAX_DOWNLOAD, CrawlPlan, Crawler, PinnedHttpsFetcher,
)


HOSTS = frozenset({'example.org'})
URL = 'https://example.org/allowed'


def address(ip):
    return (socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443))


class NativeCrawlerEgressTests(unittest.TestCase):
    def test_fetcher_requires_an_explicit_validated_allowlist(self):
        for hosts in (frozenset(), frozenset({'example.org:443'}),
                      frozenset({'EXAMPLE.ORG'}), frozenset({'example.org/other'})):
            with self.subTest(hosts=hosts), self.assertRaises(ValueError):
                PinnedHttpsFetcher(hosts)

    @patch('native_search.crawler.socket.getaddrinfo')
    def test_direct_fetcher_call_denies_unsafe_urls_before_dns(self, dns):
        fetcher = PinnedHttpsFetcher(HOSTS)
        disallowed = (
            'http://example.org/allowed',
            'https://outside.example/allowed',
            'https://example.org:443/allowed',
            'https://example.org/allowed?token=secret',
            'https://example.org/allowed#fragment',
            'https://example.org/../private',
            'https://user@example.org/allowed',
            'https://example.org\\@outside.example/allowed',
            'https://127.0.0.1/allowed',
            '',
        )
        for url in disallowed:
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetcher.fetch(url)
        dns.assert_not_called()

    @patch('native_search.crawler.socket.create_connection')
    @patch('native_search.crawler.socket.getaddrinfo')
    def test_any_nonpublic_dns_answer_denies_before_socket(self, dns, connect):
        dns.return_value = [address('8.8.8.8'), address('127.0.0.1')]
        with self.assertRaisesRegex(ValueError, 'non-public'):
            PinnedHttpsFetcher(HOSTS).fetch(URL)
        connect.assert_not_called()

    @patch('native_search.crawler.socket.create_connection')
    @patch('native_search.crawler.socket.getaddrinfo')
    def test_dns_with_only_private_addresses_denies_before_socket(self, dns, connect):
        dns.return_value = [address('10.0.0.12')]
        with self.assertRaisesRegex(ValueError, 'non-public'):
            PinnedHttpsFetcher(HOSTS).fetch(URL)
        connect.assert_not_called()

    @patch('native_search.crawler.HTTPSConnection')
    @patch('native_search.crawler.ssl.create_default_context')
    @patch('native_search.crawler.socket.create_connection')
    @patch('native_search.crawler.socket.getaddrinfo')
    def test_pins_the_checked_ip_but_preserves_tls_hostname(self, dns, connect, ssl_context, https):
        dns.return_value = [address('8.8.8.8')]
        response = Mock(status=200)
        response.read.return_value = b'page'
        response.getheader.side_effect = lambda name, default: {
            'Content-Type': 'text/html', 'X-Robots-Tag': 'noindex',
        }.get(name, default)
        https.return_value.getresponse.return_value = response

        result = PinnedHttpsFetcher(HOSTS).fetch(URL)

        self.assertEqual(200, result.status)
        self.assertEqual(b'page', result.body)
        self.assertEqual('noindex', result.robots_tag)
        dns.assert_called_once_with('example.org', 443, type=socket.SOCK_STREAM)
        connect.assert_called_once_with(('8.8.8.8', 443), timeout=8)
        ssl_context.return_value.wrap_socket.assert_called_once_with(
            connect.return_value, server_hostname='example.org')
        https.return_value.request.assert_called_once_with('GET', '/allowed', headers={
            'User-Agent': 'GoreeCloudSearchCrawler/0.1 (+https://github.com/GoreeCloud/search)',
            'Accept': 'text/html,text/plain;q=0.5',
            'Accept-Encoding': 'identity',
            'Connection': 'close',
        })
        https.return_value.close.assert_called_once()

    @patch('native_search.crawler.HTTPSConnection')
    @patch('native_search.crawler.ssl.create_default_context')
    @patch('native_search.crawler.socket.create_connection')
    @patch('native_search.crawler.socket.getaddrinfo')
    def test_response_exceeding_budget_fails_closed(self, dns, _connect, _ssl, https):
        dns.return_value = [address('8.8.8.8')]
        response = https.return_value.getresponse.return_value
        response.read.return_value = b'x' * (MAX_DOWNLOAD + 1)
        with self.assertRaisesRegex(ValueError, 'byte budget'):
            PinnedHttpsFetcher(HOSTS).fetch(URL)
        response.read.assert_called_once_with(MAX_DOWNLOAD + 1)
        https.return_value.close.assert_called_once()

    def test_default_crawler_scopes_fetcher_to_plan_hosts(self):
        plan = CrawlPlan(allowed_hosts=HOSTS)
        crawler = Crawler(index=Mock(), plan=plan)
        self.assertEqual(HOSTS, crawler.fetcher.allowed_hosts)


if __name__ == '__main__':
    unittest.main()
