# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthetic offline acceptance for GoreeCloud-owned result fusion."""

import unittest

from native_search.fusion import SourceResult, canonical_result_url, fuse_results


def hit(source, rank, url, *, category='web', media_url=None, title='Result'):
    return SourceResult(source, category, rank, url, title, media_url=media_url)


class FusionTests(unittest.TestCase):
    def test_consensus_ranks_a_cross_source_result_above_one_source(self):
        cards = [
            hit('alpha', 1, 'https://only.example/article'),
            hit('alpha', 3, 'https://shared.example/story?utm_source=feed'),
            hit('beta', 5, 'https://SHARED.example/story#paragraph'),
        ]
        results = fuse_results(cards, category='web')
        self.assertEqual(results[0].source_ranks, (('alpha', 3), ('beta', 5)))
        self.assertEqual(len(results), 2)

    def test_same_source_duplicate_is_one_vote_at_best_rank(self):
        original = hit('alpha', 4, 'https://example.com/a')
        repeated = hit('alpha', 1, 'https://example.com/a#fragment')
        merged = fuse_results([original, repeated], category='web')
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].source_ranks, (('alpha', 1),))
        self.assertAlmostEqual(merged[0].score, 1 / 61)

    def test_url_identity_preserves_semantic_parameters(self):
        self.assertEqual(canonical_result_url('https://EXAMPLE.com:443/a?ref=1&utm_medium=x#part'),
                         'https://example.com/a?ref=1')
        self.assertNotEqual(canonical_result_url('https://example.com/a?id=1'),
                            canonical_result_url('https://example.com/a?id=2'))

    def test_images_same_page_distinct_assets_do_not_collapse(self):
        cards = [
            hit('alpha', 1, 'https://example.com/gallery', category='images',
                media_url='https://cdn.example.com/one.jpg'),
            hit('alpha', 2, 'https://example.com/gallery', category='images',
                media_url='https://cdn.example.com/two.jpg'),
            hit('beta', 1, 'https://example.com/other', category='images',
                media_url='https://cdn.example.com/one.jpg#view'),
        ]
        merged = fuse_results(cards, category='images')
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].source_ranks, (('alpha', 1), ('beta', 1)))

    def test_images_missing_asset_do_not_false_merge(self):
        cards = [hit('alpha', 1, 'https://example.com/gallery', category='images'),
                 hit('beta', 1, 'https://example.com/gallery', category='images')]
        self.assertEqual(len(fuse_results(cards, category='images')), 2)

    def test_rejects_unsafe_cards_and_category_mixing(self):
        cards = [hit('alpha', 1, 'javascript:alert(1)'),
                 hit('beta', 1, 'https://user:pass@example.com/a'),
                 hit('gamma', 1, 'https://example.com/ok')]
        self.assertEqual(len(fuse_results(cards, category='web')), 1)
        with self.assertRaises(ValueError):
            fuse_results([hit('alpha', 1, 'https://example.com', category='news')], category='web')
        with self.assertRaises(ValueError):
            fuse_results([hit('alpha', 1, 'https://example.com')], category='shopping')

    def test_oversized_text_and_untrusted_media_are_skipped(self):
        cards = [
            hit('alpha', 1, 'https://example.com/a', title='X' * 513),
            SourceResult('beta', 'web', 1, 'https://example.com/b', 'Okay', 'Y' * 2001),
            hit('gamma', 1, 'https://example.com/c', category='images',
                media_url='file:///etc/passwd'),
        ]
        self.assertEqual(fuse_results(cards[:2], category='web'), [])
        self.assertEqual(fuse_results(cards[2:], category='images'), [])

    def test_invalid_rank_and_source_fail_closed(self):
        for bad in (hit('alpha', 0, 'https://example.com'),
                    hit('alpha', True, 'https://example.com'),
                    hit('not permitted', 1, 'https://example.com')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                fuse_results([bad], category='web')

    def test_deterministic_ties_and_no_hidden_network(self):
        cards = [hit('alpha', 1, 'https://example.com/first'),
                 hit('beta', 1, 'https://example.com/second')]
        self.assertEqual([r.url for r in fuse_results(cards, category='web', limit=1)],
                         ['https://example.com/first'])
        self.assertEqual(fuse_results(cards, category='web'), fuse_results(cards, category='web'))

    def test_bounded_aggregation(self):
        with self.assertRaises(ValueError):
            fuse_results((hit('alpha', 1, 'https://example.com/%d' % i)
                          for i in range(1001)), category='web')


if __name__ == '__main__':
    unittest.main()
