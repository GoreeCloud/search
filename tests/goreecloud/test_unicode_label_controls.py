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

    def test_legitimate_casefold_labels_preserve_selection(self):
        validate = policy["validate_disclosure"]
        self.assertEqual(2, validate("synthetic", ["Brave", "brave", "Startpage"],
                                     max_query_chars=100, max_providers=2))

if __name__ == "__main__":
    unittest.main()
