"""Synthetic classification of upstream HTTP denial statuses without egress."""
from timeit import default_timer
import ssl
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from curl_cffi.requests.exceptions import HTTPError, RequestException
from searx.exceptions import (
    SearxEngineAccessDeniedException,
    SearxEngineCaptchaException,
    SearxEngineTooManyRequestsException,
)
from searx.search.processors.online import (
    OnlineProcessor,
    bounded_http_provider_failure,
)


def fake_http_error(status):
    return HTTPError(
        "sensitive query and provider URL must not be copied",
        response=SimpleNamespace(status_code=status),
    )


class ProviderHttpStatusTests(unittest.TestCase):
    def test_429_is_bounded_rate_limit_and_uses_engine_suspension(self):
        with patch.object(
            SearxEngineTooManyRequestsException,
            "_get_default_suspended_time",
            return_value=3600,
        ):
            result = bounded_http_provider_failure(fake_http_error(429))
        self.assertIsInstance(result, SearxEngineTooManyRequestsException)
        self.assertEqual(3600, result.suspended_time)
        self.assertNotIn("sensitive query", str(result))
        self.assertNotIn("URL", str(result))

    def test_403_is_bounded_access_denial_and_uses_engine_suspension(self):
        with patch.object(
            SearxEngineAccessDeniedException,
            "_get_default_suspended_time",
            return_value=86400,
        ):
            result = bounded_http_provider_failure(fake_http_error(403))
        self.assertIsInstance(result, SearxEngineAccessDeniedException)
        self.assertNotIsInstance(result, SearxEngineTooManyRequestsException)
        self.assertEqual(86400, result.suspended_time)
        self.assertNotIn("sensitive query", str(result))

    def test_unknown_http_and_other_network_errors_retain_original_types(self):
        self.assertIsNone(bounded_http_provider_failure(fake_http_error(500)))
        self.assertIsNone(bounded_http_provider_failure(fake_http_error(None)))
        self.assertIsNone(bounded_http_provider_failure(HTTPError("secret", response=None)))
        self.assertIsNone(bounded_http_provider_failure(RequestException("secret")))

    def test_search_dispatches_safe_status_without_logging_query_url(self):
        worker = OnlineProcessor.__new__(OnlineProcessor)
        worker.logger = MagicMock()
        payload = fake_http_error(429)
        with (
            patch.object(worker, "init_network_in_thread"),
            patch.object(worker, "_search_basic", side_effect=payload),
            patch.object(worker, "handle_exception") as handler,
            patch.object(
                SearxEngineTooManyRequestsException,
                "_get_default_suspended_time",
                return_value=3600,
            ),
        ):
            worker.search("synthetic", {}, MagicMock(), default_timer(), 12.0)
        self.assertEqual(1, handler.call_count)
        failure = handler.call_args.args[1]
        self.assertIsInstance(failure, SearxEngineTooManyRequestsException)
        self.assertTrue(handler.call_args.kwargs["suspend"])
        log_call = worker.logger.debug.call_args
        self.assertNotIn("sensitive query", str(log_call))
        self.assertNotIn("provider URL", str(log_call))

    def test_ssl_denial_and_parser_failure_never_log_exception_payloads(self):
        private_url = 'https://provider.example.org/?q=private-phrase-123'
        cases = (
            (ssl.SSLError('TLS failure at ' + private_url), True),
            (SearxEngineAccessDeniedException(message='Access denied ' + private_url,
                                              suspended_time=5), True),
            (SearxEngineCaptchaException(message='Challenge ' + private_url,
                                         suspended_time=5), True),
            (ValueError('Failed to parse upstream body with query ' + private_url), False),
        )
        for failure, suspend in cases:
            with self.subTest(exception=type(failure).__name__):
                worker = OnlineProcessor.__new__(OnlineProcessor)
                worker.logger = MagicMock()
                with (
                    patch.object(worker, 'init_network_in_thread'),
                    patch.object(worker, '_search_basic', side_effect=failure),
                    patch.object(worker, 'handle_exception') as handler,
                ):
                    worker.search('private-phrase-123', {}, MagicMock(), default_timer(), 12.0)
                handler.assert_called_once()
                self.assertIs(failure, handler.call_args.args[1])
                self.assertEqual(suspend, handler.call_args.kwargs.get('suspend', False))
                self.assertNotIn(private_url, str(worker.logger.mock_calls))
                self.assertNotIn('private-phrase-123', str(worker.logger.mock_calls))
                self.assertIn(type(failure).__name__, str(worker.logger.debug.call_args))


if __name__ == "__main__":
    unittest.main()
