import unittest

from goreecloud_search import canonical_result_url, fuse_results


class SearchFusionTests(unittest.TestCase):
    def test_shared_result_merges_provider_evidence_and_deduplicates(self):
        merged = fuse_results({
            "alpha": [
                {"title": "Page", "url": "https://example.com/path?utm_source=alpha&x=1", "snippet": "First"},
                {"title": "Second", "url": "https://other.example/", "snippet": "Second"},
            ],
            "beta": [
                {"title": "Page again", "url": "https://EXAMPLE.com/path?x=1#section", "snippet": "Again"},
            ],
        })
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].url, "https://example.com/path?x=1")
        self.assertEqual(merged[0].engines, ("alpha", "beta"))
        self.assertEqual(merged[0].title, "Page")

    def test_rank_fusion_ignores_duplicate_entries_from_one_engine(self):
        result = fuse_results({"alpha": [
            {"title": "First", "url": "https://example.com/", "snippet": ""},
            {"title": "Duplicate", "url": "https://example.com/#part", "snippet": ""},
        ]})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].engines, ("alpha",))
        self.assertAlmostEqual(result[0].score, 1 / 61)

    def test_unsafe_result_links_never_enter_results(self):
        urls = [
            "javascript:alert(1)", "file:///etc/passwd", "https://u:p@example.com/",
            "https://localhost/", "https://example.com:99999/", "https://example.com/\nheader",
        ]
        for value in urls:
            with self.subTest(value=value):
                self.assertIsNone(canonical_result_url(value))
        rows = [{"title": "Unsafe", "url": url} for url in urls]
        self.assertEqual(fuse_results({"alpha": rows}), ())

    def test_tracking_removed_but_nontracking_query_preserved(self):
        self.assertEqual(
            canonical_result_url("HTTPS://EXAMPLE.COM:443/page?UTM_SOURCE=x&foo=bar&fbclid=123#frag"),
            "https://example.com/page?foo=bar",
        )

    def test_bad_engine_inputs_fail_explicitly(self):
        valid_row = {"title": "Valid", "url": "https://example.com/"}
        for engines in ({"Bad Name": [valid_row]}, {"valid": "not rows"}, {"valid": [valid_row] * 51}):
            with self.subTest(engines=engines), self.assertRaises(ValueError):
                fuse_results(engines)
        for limit in (0, 51, True, "10"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                fuse_results({"alpha": [valid_row]}, limit=limit)

    def test_order_independent_of_provider_input_order(self):
        a = [{"title": "A", "url": "https://a.example"}]
        b = [{"title": "B", "url": "https://b.example"}]
        forward = fuse_results({"alpha": a, "beta": b})
        reverse = fuse_results({"beta": b, "alpha": a})
        self.assertEqual(forward, reverse)


if __name__ == "__main__":
    unittest.main()
