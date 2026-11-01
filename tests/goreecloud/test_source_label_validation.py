"""Input-validation regressions for private search source fanout."""
import unittest

from searx.goreecloud_policy import (
    SearchPolicyViolation,
    distinct_selected_sources,
    validate_disclosure,
)


class SourceLabelValidationTests(unittest.TestCase):
    def test_invalid_source_labels_fail_closed(self):
        bad = (None, 3, "", " ", "brave ", " brave", "bra\nve", "bra\tve", "x" * 129)
        for label in bad:
            with self.subTest(label=repr(label)):
                with self.assertRaises(SearchPolicyViolation) as raised:
                    validate_disclosure(
                        "synthetic", ["brave", label],
                        max_query_chars=1024, max_providers=2,
                    )
                self.assertEqual(raised.exception.http_status, 422)

    def test_clean_labels_preserve_first_spelling_and_fanout(self):
        self.assertEqual(
            ["Brave", "Startpage"],
            distinct_selected_sources(["Brave", "brave", "Startpage"]),
        )
        self.assertEqual(
            2,
            validate_disclosure(
                "synthetic", ["Brave", "brave", "Startpage"],
                max_query_chars=100, max_providers=2,
            ),
        )


if __name__ == "__main__":
    unittest.main()
