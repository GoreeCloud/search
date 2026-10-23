"""DuckDuckGo Web request privacy and redirect contracts, entirely offline."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import test_runtime_smoke as _runtime_settings  # noqa: F401
from searx.engines import duckduckgo
from searx.exceptions import SearxEngineAPIException


class DuckDuckGoWebFailClosedTests(unittest.TestCase):
    def test_first_page_request_never_logs_user_query_headers_or_cookies(self):
        query = 'private-search-phrase-123'
        secret_header = 'private-header-123'
        secret_cookie = 'private-cookie-123'
        params = {
            'headers': {'X-Sensitive-Header': secret_header},
            'data': {},
            'cookies': {'private': secret_cookie},
            'pageno': 1,
            'searxng_locale': 'en-US',
            'time_range': None,
        }
        traits = SimpleNamespace(all_locale=['wt-wt'], get_region=lambda *a: 'wt-wt')
        logger = MagicMock()
        with patch.object(duckduckgo, 'traits', traits, create=True), \
                patch.object(duckduckgo, 'logger', logger, create=True):
            duckduckgo.request(query, params)

        self.assertEqual(query, params['data']['q'])
        self.assertEqual('POST', params['method'])
        logs = str(logger.mock_calls)
        for sensitive in (query, secret_header, secret_cookie):
            self.assertNotIn(sensitive, logs)
        logger.debug.assert_called_once_with('DuckDuckGo Web request prepared')

    def test_cached_vqd_is_reused_without_logging_token_or_query(self):
        token = 'private-vqd-token-123'
        query = 'private-user-query-123'
        cache = MagicMock()
        cache.secret_hash.return_value = 'opaque-hash'
        cache.get.return_value = token
        logger = MagicMock()
        with patch.object(duckduckgo, 'get_cache', return_value=cache), \
                patch.object(duckduckgo, 'logger', logger, create=True):
            result = duckduckgo.get_vqd(query, {'headers': {'User-Agent': 'synthetic'}})

        self.assertEqual(token, result)
        self.assertEqual('opaque-hash', cache.get.call_args.kwargs['key'])
        logger.debug.assert_called_once_with('get_vqd: cached token available')
        self.assertNotIn(token, str(logger.mock_calls))
        self.assertNotIn(query, str(logger.mock_calls))

    def test_unexpected_303_is_not_reported_as_empty_success(self):
        response = SimpleNamespace(status_code=303, html=MagicMock())
        with self.assertRaises(SearxEngineAPIException) as caught:
            duckduckgo.response(response)
        response.html.assert_not_called()
        self.assertEqual('DuckDuckGo Web returned unexpected redirect', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
