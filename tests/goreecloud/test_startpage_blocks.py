"""Startpage must distinguish explicit access-denied redirects from zero results."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from searx.engines import startpage
from searx.exceptions import SearxEngineAccessDeniedException, SearxEngineAPIException


def response(url="https://www.startpage.com/sp/search", location=""):
    return SimpleNamespace(url=url, headers={"Location": location}, text="<html>Blocked</html>")


class StartpageBlockTests(unittest.TestCase):
    def test_known_block_pages_are_detected(self):
        cases = (
            ("https://cdn.startpage.com/sp/cdn/error-pages/blocked.html", ""),
            ("https://www.startpage.com/", "https://cdn.startpage.com/sp/cdn/error-pages/blocked.html"),
            ("https://www.startpage.com/sp/captcha?reason=bot", ""),
        )
        for url, location in cases:
            with self.subTest(url=url, location=location):
                self.assertTrue(startpage.is_startpage_blocked_response(response(url, location)))

    def test_fake_block_hosts_and_ordinary_empty_results_are_not_misclassified(self):
        cases = (
            ("https://cdn.startpage.com.evil.example/sp/cdn/error-pages/blocked.html", ""),
            ("https://www.startpage.com/sp/search", ""),
            ("https://cdn.startpage.com/sp/cdn/help.html", ""),
        )
        for url, location in cases:
            with self.subTest(url=url):
                self.assertFalse(startpage.is_startpage_blocked_response(response(url, location)))

    def test_blocked_search_response_raises_before_parsing_empty_results(self):
        with self.assertRaises(SearxEngineAccessDeniedException):
            startpage.response(response("https://cdn.startpage.com/sp/cdn/error-pages/blocked.html"))

    def test_blocked_homepage_raises_before_form_parsing(self):
        with patch.object(startpage, 'CACHE', create=True) as cache, patch.object(
            startpage, 'get', return_value=response(
                "https://www.startpage.com/",
                "https://cdn.startpage.com/sp/cdn/error-pages/blocked.html",
            )
        ) as transport, patch.object(startpage, 'logger', create=True):
            cache.get.return_value = None
            with self.assertRaises(SearxEngineAccessDeniedException):
                startpage.get_sc_code({"headers": {}})
            transport.assert_called_once()
            cache.set.assert_not_called()

    def test_foreign_or_ambiguous_origins_cannot_supply_attributed_results(self):
        invalid = (
            "https://www.startpage.com.evil.example/sp/search",
            "https://attacker.example/sp/search?q=private-synthetic",
            "http://www.startpage.com/sp/search",
            "https://user:secret@www.startpage.com/sp/search",
            "https://www.startpage.com:8443/sp/search",
            "https://[::1]/sp/search", "https://www.startpage.com:bad/sp/search",
            "https://[broken/sp/search",
        )
        for url in invalid:
            with self.subTest(url=url), patch.object(startpage, 'extr') as parse:
                with self.assertRaises(SearxEngineAPIException) as caught:
                    startpage.response(response(url))
                parse.assert_not_called()
                self.assertEqual("Startpage returned unexpected response origin",
                                 str(caught.exception))
                self.assertNotIn('private-synthetic', str(caught.exception))

    def test_foreign_homepage_cannot_cache_form_token_or_trigger_followup(self):
        with patch.object(startpage, 'CACHE', create=True) as cache, \
                patch.object(startpage, 'get', return_value=response(
                    "https://attacker.example/?q=private-synthetic")) as transport, \
                patch.object(startpage, 'logger', create=True), \
                patch.object(startpage, 'extr') as parse:
            cache.get.return_value = None
            with self.assertRaises(SearxEngineAPIException):
                startpage.get_sc_code({"headers": {}})
            transport.assert_called_once()
            parse.assert_not_called()
            cache.set.assert_not_called()

    def test_expected_provider_origins_are_allowed_without_network(self):
        for url in ("https://www.startpage.com/sp/search",
                    "https://startpage.com/", "https://www.startpage.com:443/sp/search"):
            with self.subTest(url=url):
                self.assertIsNone(startpage.require_startpage_response_origin(response(url)))


if __name__ == "__main__":
    unittest.main()
