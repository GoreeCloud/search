from __future__ import annotations

import unittest

from goreecloud_search import parse_query
from goreecloud_search.snippets import (
    DEFAULT_SNIPPET_MAX_CHARS,
    MAX_SNIPPET_SOURCE_CHARS,
    SnippetGenerationError,
    generate_snippet,
)


class SnippetGenerationTests(unittest.TestCase):
    def test_prefers_query_match_and_keeps_output_bounded(self) -> None:
        query = parse_query('privacy "authorization travels"')
        source = (
            "GoreeCloud Search starts with a local-first result pipeline. "
            + "Background context " * 20
            + "Authorization travels with the operation, and privacy decisions remain explicit. "
            + "Trailing context " * 20
        )

        result = generate_snippet(query, source, max_chars=140)

        self.assertTrue(result.matched_query)
        self.assertIn("Authorization travels", result.text)
        self.assertLessEqual(len(result.text), 140)
        self.assertGreater(result.start_offset, 0)
        self.assertLess(result.end_offset, len(" ".join(source.split())))

    def test_no_match_prefers_complete_leading_sentence(self) -> None:
        query = parse_query("unmatched")
        result = generate_snippet(
            query,
            "GoreeCloud Search keeps result processing deterministic. A second sentence follows.",
        )

        self.assertFalse(result.matched_query)
        self.assertEqual(
            result.text,
            "GoreeCloud Search keeps result processing deterministic.…",
        )
        self.assertEqual(result.start_offset, 0)

    def test_source_is_whitespace_normalized_and_input_is_not_retained(self) -> None:
        query = parse_query("search")
        source = "  GoreeCloud\n\tSearch   generates   snippets.  "

        result = generate_snippet(query, source)

        self.assertEqual(result.text, "GoreeCloud Search generates snippets.")
        self.assertFalse(result.source_truncated)
        self.assertNotIn("\n", result.text)
        self.assertNotIn("\t", result.text)
        self.assertFalse(hasattr(result, "source_text"))

    def test_unsafe_display_controls_are_removed(self) -> None:
        query = parse_query("invoice")
        result = generate_snippet(
            query,
            "Invoice\u202efdp.exe\u2066 is ready.\x00 Continue safely.",
        )

        self.assertEqual(result.text, "Invoice fdp.exe is ready. Continue safely.")
        self.assertNotIn("\u202e", result.text)
        self.assertNotIn("\u2066", result.text)
        self.assertNotIn("\x00", result.text)

    def test_ordinary_unicode_shaping_is_preserved(self) -> None:
        source = "Family 👩‍💻 workflows remain readable."
        result = generate_snippet(parse_query("family"), source)

        self.assertIn("👩‍💻", result.text)

    def test_source_processing_is_capped_before_generation(self) -> None:
        query = parse_query("needle")
        source = "a" * MAX_SNIPPET_SOURCE_CHARS + " needle after the processing cap"

        result = generate_snippet(query, source)

        self.assertTrue(result.source_truncated)
        self.assertFalse(result.matched_query)
        self.assertLessEqual(len(result.text), DEFAULT_SNIPPET_MAX_CHARS)
        self.assertNotIn("needle", result.text.casefold())

    def test_rejects_unbounded_too_small_or_non_integer_output_requests(self) -> None:
        query = parse_query("goreecloud")
        for invalid in (79, DEFAULT_SNIPPET_MAX_CHARS + 1, True, 120.5):
            with self.subTest(invalid=invalid):
                with self.assertRaises(SnippetGenerationError):
                    generate_snippet(query, "GoreeCloud", max_chars=invalid)

    def test_empty_source_returns_empty_metadata_only_result(self) -> None:
        result = generate_snippet(parse_query("anything"), " \n\t ")

        self.assertEqual(result.text, "")
        self.assertFalse(result.matched_query)
        self.assertEqual(result.start_offset, 0)
        self.assertEqual(result.end_offset, 0)


if __name__ == "__main__":
    unittest.main()
