"""Regression coverage for search syntax and post-normalization result constraints."""

import unittest

from goreecloud_search import (
    NormalizedResult,
    QueryParseError,
    ProviderOrigin,
    ResultProvenance,
    parse_query,
    rank_results,
)


def candidate(result_id: str, title: str, url: str, snippet: str = "") -> NormalizedResult:
    return NormalizedResult(
        result_id=result_id,
        title=title,
        url=url,
        canonical_url=url,
        snippet=snippet,
        published_at=None,
        content_type=None,
        language=None,
        source_agreement=1,
        provenance=(
            ResultProvenance(
                provider="index",
                origin=ProviderOrigin.GOREECLOUD_INDEX,
                provider_rank=None,
                source_id=None,
                contract_version=None,
                indexed_by_goreecloud=True,
                content_hash=None,
                last_crawled_at=None,
            ),
        ),
    )


class QuotedQueryTests(unittest.TestCase):
    def test_quoted_operator_remains_literal_phrase(self) -> None:
        parsed = parse_query('"site:example.com" privacy')
        self.assertEqual(parsed.phrases, ("site:example.com",))
        self.assertEqual(parsed.filters.sites, ())
        self.assertEqual(parsed.terms, ("privacy",))

    def test_negative_quoted_phrase_is_single_exclusion(self) -> None:
        parsed = parse_query('reports -"data broker" -"AD Tracking"')
        self.assertEqual(parsed.excluded_terms, ("data broker", "AD Tracking"))
        self.assertEqual(parsed.terms, ("reports",))

    def test_quoted_escaped_text(self) -> None:
        parsed = parse_query('privacy -"quoted \\"example\\""')
        self.assertEqual(parsed.excluded_terms, ('quoted "example"',))

    def test_rejects_unterminated_and_adjacent_quotes(self) -> None:
        for raw in (
            'privacy "unterminated phrase',
            'privacy -"unterminated phrase',
            'privacy "phrase"tail',
            'privacy foo"bar',
            'privacy -""',
        ):
            with self.subTest(raw=raw), self.assertRaises(QueryParseError):
                parse_query(raw)


class ResultFilterTests(unittest.TestCase):
    def test_site_restriction_is_enforced_not_merely_boosted(self) -> None:
        query = parse_query("report site:example.com")
        results = (
            candidate("other", "Report", "https://example.com.evil.test/report.pdf"),
            candidate("subdomain", "Report", "https://docs.example.com/report.pdf"),
            candidate("root", "Report", "https://example.com/report.pdf"),
        )
        self.assertEqual(
            {item.result.result_id for item in rank_results(query, results)},
            {"subdomain", "root"},
        )

    def test_excluded_domains_match_subdomains_but_not_suffix_lookalikes(self) -> None:
        query = parse_query("privacy -domain:ads.example")
        results = (
            candidate("blocked", "Privacy", "https://tracking.ads.example/"),
            candidate("root", "Privacy", "https://ads.example/"),
            candidate("allowed", "Privacy", "https://notads.example/"),
        )
        self.assertEqual(
            [item.result.result_id for item in rank_results(query, results)],
            ["allowed"],
        )

    def test_filetype_constraint_matches_url_path_not_query(self) -> None:
        query = parse_query("report filetype:pdf")
        results = (
            candidate("html", "Report", "https://example.com/report.html?format=.pdf"),
            candidate("pdf", "Report", "https://example.com/report.PDF?view=1"),
        )
        self.assertEqual([item.result.result_id for item in rank_results(query, results)], ["pdf"])

    def test_negative_terms_use_word_boundaries_in_display_text(self) -> None:
        query = parse_query("security -ads")
        results = (
            candidate("bad-title", "Security Ads", "https://example.com/a"),
            candidate("bad-snippet", "Security", "https://example.com/b", "Contains ADS"),
            candidate("good", "Security", "https://example.com/c", "Safe downloads"),
        )
        self.assertEqual([item.result.result_id for item in rank_results(query, results)], ["good"])

    def test_negative_quoted_phrase_matches_visible_text_only(self) -> None:
        query = parse_query('privacy -"data broker"')
        results = (
            candidate("blocked", "Privacy", "https://example.com/a", "Protect against DATA BROKER listings"),
            candidate("allowed", "Privacy", "https://example.com/b", "Data protection guides"),
        )
        self.assertEqual([item.result.result_id for item in rank_results(query, results)], ["allowed"])

    def test_no_filter_preserves_default_relevance_order(self) -> None:
        query = parse_query("search engine")
        results = (
            candidate("b", "Other", "https://b.example/"),
            candidate("a", "Search engine", "https://a.example/"),
        )
        self.assertEqual(
            [item.result.result_id for item in rank_results(query, results)],
            ["a", "b"],
        )


if __name__ == "__main__":
    unittest.main()
