"""Dependency-free Unicode spoofing regressions for private search labels."""
import runpy
import unittest
from pathlib import Path

policy = runpy.run_path(str(Path(__file__).resolve().parents[2] / "searx/goreecloud_policy.py"))

class UnicodeLabelControlTests(unittest.TestCase):
    def test_invisible_and_bidi_controls_are_rejected_before_fanout(self):
        validate = policy["validate_disclosure"]
        violation = policy["SearchPolicyViolation"]
        for codepoint in (0x200D, 0x202E, 0x2066, 0x2028, 0x2029, 0x001F):
            label = "bra" + chr(codepoint) + "ve"
            with self.subTest(codepoint=hex(codepoint)):
                with self.assertRaises(violation) as caught:
                    validate("synthetic", ["brave", label],
                             max_query_chars=100, max_providers=2)
                self.assertEqual(422, caught.exception.http_status)

    def test_unpaired_surrogates_rejected_in_provider_labels_and_result_urls(self):
        validate = policy["validate_disclosure"]
        violation = policy["SearchPolicyViolation"]
        allowed_link = policy["safe_primary_result_url"]
        for codepoint in (0xD800, 0xDC00):
            with self.subTest(codepoint=hex(codepoint)):
                with self.assertRaises(violation) as caught:
                    validate("synthetic", ["safe", "sa" + chr(codepoint) + "fe"],
                             max_query_chars=100, max_providers=2)
                self.assertEqual(422, caught.exception.http_status)
                self.assertFalse(allowed_link("https://example.invalid/" + chr(codepoint)))
        self.assertTrue(allowed_link("https://example.invalid/valid"))

    def test_legitimate_casefold_labels_preserve_selection(self):
        validate = policy["validate_disclosure"]
        self.assertEqual(2, validate("synthetic", ["Brave", "brave", "Startpage"],
                                     max_query_chars=100, max_providers=2))

if __name__ == "__main__":
    unittest.main()

class SearchBoundaryTypeTests(unittest.TestCase):
    def test_malformed_query_and_source_container_fail_before_disclosure(self):
        validate = policy["validate_disclosure"]
        violation = policy["SearchPolicyViolation"]
        for query in (None, b"private", "private" + chr(0xD800)):
            with self.subTest(query_type=type(query).__name__):
                with self.assertRaises(violation) as caught:
                    validate(query, ["Brave"], max_query_chars=200, max_providers=2)
                self.assertEqual(caught.exception.http_status, 422)
        for sources in ("Brave", b"Brave", None):
            with self.subTest(sources_type=type(sources).__name__):
                with self.assertRaises(violation):
                    validate("private", sources, max_query_chars=200, max_providers=2)

    def test_result_links_reject_unicode_whitespace(self):
        safe = policy["safe_primary_result_url"]
        for separator in ("\u00a0", "\u2003", "\u202f"):
            with self.subTest(separator=repr(separator)):
                self.assertFalse(safe("https://example.invalid/path" + separator + "term"))
        self.assertTrue(safe("https://example.invalid/path%20term"))
