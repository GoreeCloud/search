"""Offline provider-independent regression for GoreeCloud Search tracker cleanup."""
import unittest
from unittest.mock import Mock, patch

from searx.data.tracker_patterns import TrackerPatternsDB


class OfflineTrackerRulesTests(unittest.TestCase):
    def setUp(self):
        # No SQLite/cache initializer or outbound access is necessary.
        self.db = object.__new__(TrackerPatternsDB)

    def test_branded_search_never_fetches_remote_rules_even_if_privacy_flag_false(self):
        for branding in ({"private_search": True}, {"private_search": False},
                         {"require_anonymous_egress": False}):
            with self.subTest(branding=branding), patch(
                "searx.data.tracker_patterns.get_setting", return_value=branding
            ), patch("searx.data.tracker_patterns.http_get") as get:
                rules = list(self.db.iter_clear_list())
                self.assertEqual([TrackerPatternsDB.GOREECLOUD_OFFLINE_RULE], rules)
                get.assert_not_called()

    def test_tracking_parameters_removed_without_mutating_meaningful_query(self):
        with patch.object(self.db, "rules",
                          return_value=iter((TrackerPatternsDB.GOREECLOUD_OFFLINE_RULE,))):
            result = self.db.clean_url(
                "https://public.example.org/path?id=123&utm_source=newsletter&"
                "fbclid=synthetic-private-value&gclid=synthetic-other-value#section"
            )
            self.assertEqual(
                "https://public.example.org/path?id=123#section", result
            )

    def test_no_matching_tracking_parameters_leave_url_unchanged(self):
        with patch.object(self.db, "rules",
                          return_value=iter((TrackerPatternsDB.GOREECLOUD_OFFLINE_RULE,))):
            self.assertIs(True, self.db.clean_url(
                "https://public.example.org/path?q=research&ref=article"
            ))

    def test_cleanup_logging_never_exposes_result_host_or_tracking_value(self):
        with patch.object(self.db, "rules",
                          return_value=iter((TrackerPatternsDB.GOREECLOUD_OFFLINE_RULE,))), patch(
                              "searx.data.tracker_patterns.log"
                          ) as logger:
            self.db.clean_url(
                "https://private-result-host.example.org/?utm_source=private-marker-123"
            )
        self.assertNotIn("private-marker-123", repr(logger.mock_calls))
        self.assertNotIn("private-result-host.example.org", repr(logger.mock_calls))

    def test_nonbranded_searxng_retains_default_rule_source(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "providers": {"fixture": {
                "urlPattern": r"^https://example\\.org/",
                "exceptions": [],
                "rules": ["^fixture$"],
            }}
        }
        with patch("searx.data.tracker_patterns.get_setting", return_value=None), patch(
            "searx.data.tracker_patterns.http_get", return_value=response
        ) as get:
            rules = list(self.db.iter_clear_list())
        self.assertEqual(1, get.call_count)
        self.assertEqual(["^fixture$"], rules[0][2])


if __name__ == "__main__":
    unittest.main()
