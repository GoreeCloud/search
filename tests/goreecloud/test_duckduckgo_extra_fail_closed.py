"""Offline regression for DuckDuckGo media denial; no provider requests.

A missing VQD is not license to send a second malformed request.
"""
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_runtime_smoke as _runtime_settings  # noqa: F401
from searx.engines import duckduckgo_extra as extra
from searx.exceptions import (
    SearxEngineAPIException,
    SearxEngineAccessDeniedException,
    SearxEngineTooManyRequestsException,
)


def params():
    return {
        "headers": {},
        "cookies": {},
        "data": {},
        "url": None,
        "pageno": 1,
        "safesearch": 1,
        "searxng_locale": "en-US",
    }


class DuckDuckGoExtraFailClosedTests(unittest.TestCase):
    def setUp(self):
        # Normally injected by the SearXNG engine loader.
        mock_logger = patch.object(extra, 'logger', logging.getLogger('synthetic.ddg'), create=True)
        mock_logger.start()
        self.addCleanup(mock_logger.stop)

    def test_http_403_is_access_denied_and_does_not_cache_token(self):
        p = params()
        with patch.object(extra, "get", return_value=SimpleNamespace(status_code=403, text="denied")) as get, \
                patch.object(extra, "set_vqd") as cache:
            with self.assertRaises(SearxEngineAccessDeniedException):
                extra.fetch_vqd("public photos", p)
            self.assertEqual(1, get.call_count)
            cache.assert_not_called()

    def test_http_429_is_rate_limited_with_no_followup(self):
        p = params()
        with patch.object(extra, "get", return_value=SimpleNamespace(status_code=429, text="blocked")) as get, \
                patch.object(extra, "set_vqd") as cache:
            with self.assertRaises(SearxEngineTooManyRequestsException):
                extra.fetch_vqd("public photos", p)
            get.assert_called_once()
            cache.assert_not_called()

    def test_other_error_status_is_not_reinterpreted_as_captcha(self):
        for status in (400, 404, 500, 503):
            with self.subTest(status=status):
                with patch.object(extra, "get", return_value=SimpleNamespace(status_code=status, text="")):
                    with self.assertRaises(SearxEngineAPIException) as caught:
                        extra.fetch_vqd("public photos", params())
                    self.assertNotIsInstance(caught.exception, SearxEngineAccessDeniedException)

    def test_no_vqd_in_successful_html_is_an_explicit_error(self):
        with patch.object(extra, "get", return_value=SimpleNamespace(status_code=200, text="normal page")), \
                patch.object(extra, "set_vqd") as cache:
            with self.assertRaisesRegex(SearxEngineAPIException, "token unavailable"):
                extra.fetch_vqd("public photos", params())
            cache.assert_not_called()

    def test_successful_vqd_is_cached_once_without_logging_token(self):
        p = params()
        secret = "synthetic-test-vqd-only"
        with patch.object(extra, "get", return_value=SimpleNamespace(
                status_code=200, text='<html>vqd="' + secret + '"</html>')), \
                patch.object(extra, "set_vqd") as cache, \
                patch.object(extra.logger, "debug") as debug:
            actual = extra.fetch_vqd("public photos", p)
            self.assertEqual(secret, actual)
            cache.assert_called_once_with(query="public photos", value=secret, params=p)
            self.assertNotIn(secret, str(debug.call_args_list))

    def test_no_cached_token_and_empty_fetched_token_blocks_json_request(self):
        p = params()
        with patch.object(extra, "get_vqd", return_value=""), \
                patch.object(extra, "fetch_vqd", return_value="") as fetch:
            with self.assertRaisesRegex(SearxEngineAPIException, "token unavailable"):
                extra.request("public photos", p)
            fetch.assert_called_once()
            self.assertIsNone(p["url"])

    def test_access_denied_is_propagated_not_retried(self):
        p = params()
        with patch.object(extra, "get_vqd", return_value=""), \
                patch.object(extra, "fetch_vqd", side_effect=SearxEngineAccessDeniedException(
                    suspended_time=1, message="test-only denial")) as fetch:
            with self.assertRaises(SearxEngineAccessDeniedException):
                extra.request("public photos", p)
            fetch.assert_called_once()
            self.assertIsNone(p["url"])

    def test_unrelated_empty_or_oversized_queries_do_not_contact_provider(self):
        p = params()
        with patch.object(extra, "get") as outbound, patch.object(extra, "get_vqd") as cached:
            extra.request("x"*500, p)
            self.assertIsNone(p["url"])
            outbound.assert_not_called()
            cached.assert_not_called()


if __name__ == "__main__":
    unittest.main()
