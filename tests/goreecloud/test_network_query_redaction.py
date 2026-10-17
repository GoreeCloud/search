"""Regression coverage for search terms in the upstream HTTP network logger."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from searx.network.network import Network


class SearchNetworkLoggingRedactionTests(unittest.TestCase):
    def test_locale_url_is_absent_from_debug_log(self):
        from pathlib import Path
        path = Path(__file__).resolve().parents[2] / "searx/webapp.py"
        source = path.read_text(encoding="utf-8")
        section = source.split("def get_locale():", 1)[1].split("\n\n", 1)[0]
        self.assertNotIn("sxng_request.url", section)
        self.assertIn('logger.debug("Locale selected: %s", locale)', section)

    def test_failure_and_debug_logs_never_include_query_url(self):
        needle = "sensitive-synthetic-query-needle"
        url = "https://search.example/search?q=" + needle
        response = SimpleNamespace(
            request=SimpleNamespace(method="GET", url=url),
            url=url, status_code=429, reason="Too Many Requests",
            headers={"Content-Type": "text/html"}, http_version=2,
        )
        network = Network()
        network._logger = Mock()
        with patch("searx.network.network.raise_for_httperror",
                   side_effect=ValueError("upstream response rejected")):
            with self.assertRaises(ValueError):
                network.patch_response(response, True)
        asyncio.run(network.log_response(response))
        calls = str(network._logger.mock_calls)
        self.assertNotIn(needle, calls)
        self.assertNotIn(url, calls)
        self.assertIn("status=%s", calls)
        self.assertIn("429", calls)


if __name__ == "__main__":
    unittest.main()