# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthetic offline acceptance for GoreeCloud-owned result fusion."""

import unittest

from native_search.fusion import (
    SourceResult, canonical_result_url, fuse_results, video_result_identity,
)


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

    def test_youtube_video_variants_merge_across_sources_without_losing_destination(self):
        clip = 'aBc_123-XyZ'
        cards = [
            hit('alpha', 1, 'https://www.youtube.com/watch?v=' + clip + '&t=90s',
                category='videos'),
            hit('beta', 2, 'https://youtu.be/' + clip + '?si=synthetic',
                category='videos'),
            hit('gamma', 3, 'https://m.youtube.com/shorts/' + clip,
                category='videos'),
            hit('delta', 4, 'https://www.youtube-nocookie.com/embed/' + clip,
                category='videos'),
        ]
        fused = fuse_results(cards, category='videos')
        self.assertEqual(1, len(fused))
        self.assertEqual(4, len(fused[0].source_ranks))
        self.assertEqual(cards[0].url, fused[0].url)
        self.assertEqual('video:youtube:' + clip, video_result_identity(cards[0].url))
        self.assertEqual(video_result_identity(cards[0].url),
                         video_result_identity(cards[1].url))

    def test_video_identity_is_conservative_about_other_links_and_ambiguous_ids(self):
        urls = [
            'https://www.youtube.com/watch?v=aBc_123-XyZ&v=Different1',
            'https://www.youtube.com/@channel/videos',
            'https://www.youtube.com/watch?v=short',
            'https://www.youtube.com.evil.test/watch?v=aBc_123-XyZ',
            'https://www.youtube.com:444/watch?v=aBc_123-XyZ',
            'https://youtu.be/aBc_123-XyZ/extra',
            'https://www.youtube.com/watch?v=Different1X',
        ]
        self.assertEqual(len(urls), len(set(map(video_result_identity, urls))))
        self.assertEqual(2, len(fuse_results([
            hit('alpha', 1, urls[3], category='videos'),
            hit('beta', 1, 'https://youtu.be/aBc_123-XyZ', category='videos'),
        ], category='videos')))

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

    def test_explicit_query_promotes_relevant_title_over_nearby_irrelevant_rank(self):
        cards = [
            hit('alpha', 1, 'https://example.org/advertisement', title='Sponsored landing page'),
            hit('alpha', 2, 'https://example.org/search-guide', title='GoreeCloud Search Guide'),
        ]
        # Legacy no-query RRF remains untouched for every existing caller.
        original = fuse_results(cards, category='web')
        self.assertEqual(cards[0].url, original[0].url)
        self.assertEqual(1 / 61, original[0].score)
        self.assertEqual(original, fuse_results(cards, category='web', query=None))
        ranked = fuse_results(cards, category='web', query='goreecloud search')
        self.assertEqual(cards[1].url, ranked[0].url)
        self.assertEqual((('alpha', 2),), ranked[0].source_ranks)
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_relevance_credit_is_repeat_insensitive_and_strictly_capped(self):
        relevant = hit('alpha', 1, 'https://example.org/guide', title='Cloud Cloud Cloud')
        stuffing = hit('alpha', 1, 'https://example.org/guide', title='Cloud ' * 40)
        base = fuse_results([relevant], category='web')[0].score
        ordinary = fuse_results([relevant], category='web', query='cloud')[0]
        repeated = fuse_results([stuffing], category='web', query='cloud')[0]
        self.assertEqual(ordinary.score, repeated.score)
        self.assertLessEqual(ordinary.score - base, 0.2 / 61 + 1e-12)
        # A repeat from the SAME provider never gains another fusion vote.
        both = fuse_results([relevant, stuffing], category='web', query='cloud')[0]
        self.assertEqual((('alpha', 1),), both.source_ranks)
        self.assertEqual(ordinary.score, both.score)

    def test_query_cannot_override_strong_distinct_source_consensus(self):
        cards = [
            hit('alpha', 1, 'https://example.org/consensus', title='Independent factual overview'),
            hit('beta', 1, 'https://example.org/consensus#part', title='Same overview'),
            hit('gamma', 1, 'https://example.org/marketing', title='GoreeCloud Search Guide'),
        ]
        ranked = fuse_results(cards, category='web', query='goreecloud search')
        self.assertEqual('https://example.org/consensus', ranked[0].url)
        self.assertEqual((('alpha', 1), ('beta', 1)), ranked[0].source_ranks)

    def test_query_matches_whole_unicode_words_not_substrings(self):
        cards = [
            hit('alpha', 1, 'https://example.org/only-substring', title='Artisan painting'),
            hit('alpha', 2, 'https://example.org/full-token', title='Art forms'),
        ]
        ranked = fuse_results(cards, category='web', query='art')
        self.assertEqual('https://example.org/full-token', ranked[0].url)
        other = [
            hit('alpha', 1, 'https://example.org/untouched', title='Alternative routes'),
            hit('alpha', 2, 'https://example.org/german', title='Straße network'),
        ]
        self.assertEqual('https://example.org/german', fuse_results(
            other, category='web', query='STRASSE')[0].url)

    def test_optional_description_matches_less_than_title(self):
        cards = [
            SourceResult('alpha', 'web', 1, 'https://example.org/a', 'Other page',
                         'GoreeCloud search'),
            SourceResult('beta', 'web', 1, 'https://example.org/b', 'GoreeCloud search', ''),
        ]
        fused = fuse_results(cards, category='web', query='goreecloud search')
        self.assertEqual('https://example.org/b', fused[0].url)

    def test_relevance_query_is_bounded_and_fails_closed(self):
        card = hit('alpha', 1, 'https://example.org/a')
        invalid = (True, 123, '', '\n', 'bad\nquery', 'x' * 513,
                   ' '.join('term%d' % index for index in range(17)),
                   'a' * 65)
        for query in invalid:
            with self.subTest(query=str(query)[:30]), self.assertRaises(ValueError):
                fuse_results([card], category='web', query=query)
        self.assertEqual(1, len(fuse_results([card], category='web', query='hello')))


if __name__ == '__main__':
    unittest.main()
