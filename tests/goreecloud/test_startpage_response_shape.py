"""Startpage must distinguish genuine empty pages from upstream layout drift.

All responses are synthetic; no provider calls, cookies or user queries.
"""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from searx.engines import startpage
from searx.exceptions import SearxEngineXPathException
from searx.results import UnresponsiveEngine
from searx.webutils import get_translated_errors


def fixture(payload):
    # The upstream parser reconstructs the two final closing braces from the
    # embedded React presenter. Keep the extraction seam deterministic.
    text = json.dumps(payload)
    assert text.endswith("}}")
    return text[1:-2]


class StartpageResponseShapeTests(unittest.TestCase):
    def parse(self, payload):
        response = SimpleNamespace(
            url="https://www.startpage.com/sp/search",
            headers={},
            text="<html><body>synthetic presenter only</body></html>",
        )
        with patch.object(startpage, "extr", return_value=fixture(payload)):
            return startpage.response(response)

    def test_explicit_empty_mainline_is_valid_zero_results(self):
        self.assertEqual([], self.parse({
            "render": {"presenter": {"regions": {"mainline": []}}}
        }))

    def test_empty_group_with_explicit_result_list_is_valid(self):
        self.assertEqual([], self.parse({
            "render": {"presenter": {"regions": {
                "mainline": [{"display_type": "web-google", "results": []}]
            }}}
        }))

    def test_missing_or_invalid_presenter_is_parsing_failure(self):
        cases = (
            {"render": {}},
            {"render": {"presenter": {}}},
            {"render": {"presenter": {"regions": {}}}},
            {"render": {"presenter": {"regions": {"mainline": None}}}},
            {"render": {"presenter": {"regions": {"mainline": {}}}}},
            {"render": {"presenter": {"regions": {"mainline": [None]}}}},
            {"render": {"presenter": {"regions": {
                "mainline": [{"display_type": "web-google"}]
            }}}},
            {"render": {"presenter": {"regions": {
                "mainline": [{"display_type": "web-google", "results": [None]}]
            }}}},
        )
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(SearxEngineXPathException):
                self.parse(payload)

    def test_valid_web_result_survives_shape_guard(self):
        results = self.parse({"render": {"presenter": {"regions": {
            "mainline": [{"display_type": "web-google", "results": [{
                "clickUrl": "https://example.org/",
                "title": "Synthetic result",
                "description": "Synthetic description",
            }]}]
        }}}})
        self.assertEqual(1, len(results))
        self.assertEqual("https://example.org/", results[0]["url"])
        self.assertEqual("Synthetic result", results[0]["title"])

    def test_error_is_visible_as_parsing_not_unexpected_crash(self):
        diagnostic = get_translated_errors([UnresponsiveEngine(
            "startpage", "searx.exceptions.SearxEngineXPathException", False
        )])
        self.assertEqual(1, len(diagnostic))
        self.assertNotIn("unexpected crash", diagnostic[0][1].lower())


if __name__ == "__main__":
    unittest.main()
