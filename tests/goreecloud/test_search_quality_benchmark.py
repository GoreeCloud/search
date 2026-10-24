"""Synthetic quality diagnostics for independently fused GoreeCloud results."""

from copy import deepcopy
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import search_quality_benchmark as quality


FIXTURE = (Path(__file__).parent / 'fixtures' / 'search_quality'
           / 'images_multi_source.json')


def images():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class SearchQualityBenchmarkTests(unittest.TestCase):
    def test_multi_source_images_are_deduplicated_by_media_not_page(self):
        result = quality.evaluate_fixture(images())
        self.assertTrue(result['passed'])
        self.assertEqual(6, result['candidate_count'])
        self.assertEqual(4, result['distinct_results'])
        self.assertEqual(2, result['collapsed_duplicates'])
        self.assertEqual(2, result['contributing_sources'])
        self.assertEqual(2, result['sources_with_unique_at_10'])
        self.assertEqual(2, result['unique_results_at_10'])
        self.assertEqual(3, result['relevant_at_10'])
        self.assertEqual(100, result['recall_percent_at_10'])
        self.assertEqual(30, result['precision_percent_at_10'])
        self.assertEqual(0, result['missing_image_media_identity'])
        self.assertFalse(result['release_qualified'])

    def test_timeout_cannot_silently_fall_back_to_single_image_provider(self):
        fixture = images()
        fixture['sources'][1]['state'] = 'timeout'
        fixture['sources'][1]['results'] = []
        result = quality.evaluate_fixture(fixture)
        self.assertFalse(result['passed'])
        self.assertEqual(['synthetic_beta'], result['failed_sources'])
        self.assertIn('insufficient_contributing_sources', result['failed_gates'])
        self.assertIn('source_degraded', result['failed_gates'])
        self.assertNotIn('synthetic_b.jpg', str(result))

    def test_two_mirrored_sources_do_not_count_as_independent_discovery(self):
        fixture = images()
        fixture['sources'][1]['results'] = [dict(row) for row in
                                          fixture['sources'][0]['results']]
        fixture['relevant'] = [
            'https://assets.example.test/a.jpg',
            'https://assets.example.test/b.jpg',
            'https://assets.example.test/c.jpg',
        ]
        fixture['gates']['min_distinct'] = 3
        fixture['gates']['min_sources_with_unique_at_10'] = 1
        outcome = quality.evaluate_fixture(fixture)
        self.assertEqual(2, outcome['contributing_sources'])
        self.assertEqual(0, outcome['sources_with_unique_at_10'])
        self.assertEqual(0, outcome['unique_results_at_10'])
        self.assertFalse(outcome['passed'])
        self.assertEqual(['insufficient_unique_source_discovery_at_10'],
                         outcome['failed_gates'])

    def test_images_with_distinct_discoveries_from_both_sources_pass_gate(self):
        fixture = images()
        fixture['gates']['min_sources_with_unique_at_10'] = 2
        outcome = quality.evaluate_fixture(fixture)
        self.assertTrue(outcome['passed'])
        self.assertEqual(2, outcome['sources_with_unique_at_10'])

    def test_video_relevance_judgments_merge_canonical_video_variants(self):
        clip = 'aBc_123-XyZ'
        fixture = {
            'development_only': True, 'category': 'videos',
            'sources': [
                {'source': 'synthetic_alpha', 'state': 'ok', 'results': [
                    {'rank': 1, 'url': 'https://www.youtube.com/watch?v=' + clip,
                     'title': 'Synthetic clip'},
                    {'rank': 2, 'url': 'https://videos.example.test/clip-one',
                     'title': 'Independent video one'},
                ]},
                {'source': 'synthetic_beta', 'state': 'ok', 'results': [
                    {'rank': 1, 'url': 'https://youtu.be/' + clip,
                     'title': 'Same synthetic clip'},
                    {'rank': 2, 'url': 'https://videos.example.test/clip-two',
                     'title': 'Independent video two'},
                ]},
            ],
            'relevant': [
                'https://youtube.com/shorts/' + clip,
                'https://videos.example.test/clip-two',
            ],
            'gates': {
                'min_distinct': 3, 'min_contributing_sources': 2,
                'min_relevant_at_10': 2, 'min_recall_percent_at_10': 100,
                'max_missing_image_media': 0,
                'min_sources_with_unique_at_10': 2,
                'require_all_sources_healthy': True,
            },
        }
        outcome = quality.evaluate_fixture(fixture)
        self.assertTrue(outcome['passed'])
        self.assertEqual(4, outcome['candidate_count'])
        self.assertEqual(3, outcome['distinct_results'])
        self.assertEqual(1, outcome['collapsed_duplicates'])
        self.assertEqual(2, outcome['relevant_at_10'])
        self.assertEqual(100, outcome['recall_percent_at_10'])
        self.assertEqual(2, outcome['sources_with_unique_at_10'])

    def test_explicit_empty_is_not_upstream_failure_but_lowers_coverage(self):
        fixture = images()
        fixture['sources'][1]['state'] = 'empty'
        fixture['sources'][1]['results'] = []
        result = quality.evaluate_fixture(fixture)
        self.assertFalse(result['passed'])
        self.assertEqual([], result['failed_sources'])
        self.assertEqual(['synthetic_beta'], result['empty_sources'])
        self.assertIn('insufficient_contributing_sources', result['failed_gates'])
        self.assertNotIn('source_degraded', result['failed_gates'])

    def test_missing_original_image_url_is_not_counted_as_quality_pass(self):
        fixture = images()
        fixture['sources'][0]['results'][0].pop('media_url')
        result = quality.evaluate_fixture(fixture)
        self.assertFalse(result['passed'])
        self.assertEqual(1, result['missing_image_media_identity'])
        self.assertIn('missing_image_media_identity', result['failed_gates'])

    def test_inadequate_judged_relevance_fails_closed(self):
        fixture = images()
        fixture['relevant'][0] = 'https://assets.example.test/relevant-not-returned.jpg'
        result = quality.evaluate_fixture(fixture)
        self.assertFalse(result['passed'])
        self.assertEqual(2, result['relevant_at_10'])
        self.assertEqual(66, result['recall_percent_at_10'])
        self.assertIn('insufficient_relevant_at_10', result['failed_gates'])
        self.assertIn('insufficient_recall_at_10', result['failed_gates'])

    def test_optional_first_relevant_rank_gate_catches_top_heavy_bad_ranking(self):
        fixture = images()
        # One judged-relevant card does occur in the displayed top ten, but
        # source consensus puts it fourth. Recall alone would incorrectly
        # report a passing fixture despite poor first-result relevance.
        fixture['relevant'] = ['https://assets.example.test/c.jpg']
        fixture['gates']['min_relevant_at_10'] = 1
        fixture['gates']['min_reciprocal_rank_percent_at_10'] = 50
        outcome = quality.evaluate_fixture(fixture)
        self.assertEqual(1, outcome['relevant_at_10'])
        self.assertEqual(100, outcome['recall_percent_at_10'])
        self.assertEqual(25, outcome['reciprocal_rank_percent_at_10'])
        self.assertEqual(['insufficient_first_relevant_rank_at_10'],
                         outcome['failed_gates'])
        fixture['gates']['min_reciprocal_rank_percent_at_10'] = 25
        self.assertTrue(quality.evaluate_fixture(fixture)['passed'])

    def test_reciprocal_rank_gate_rejects_non_integer_or_unachievable_bounds(self):
        for value in (True, False, 0, -1, 101, '50', 12.5):
            fixture = images()
            fixture['gates']['min_reciprocal_rank_percent_at_10'] = value
            with self.subTest(value=value), self.assertRaises(quality.InvalidBenchmark):
                quality.evaluate_fixture(fixture)

    def test_web_same_source_repeat_is_one_vote_and_one_result(self):
        fixture = {
            'development_only': True, 'category': 'web',
            'sources': [
                {'source': 'synthetic_alpha', 'state': 'ok', 'results': [
                    {'rank': 1, 'url': 'https://example.test/page?utm_source=alpha',
                     'title': 'First'},
                    {'rank': 2, 'url': 'https://example.test/page', 'title': 'Repeat'},
                ]},
                {'source': 'synthetic_beta', 'state': 'ok', 'results': [
                    {'rank': 1, 'url': 'https://example.test/page', 'title': 'Other'},
                ]},
            ],
            'relevant': ['https://example.test/page'],
            'gates': {
                'min_distinct': 1, 'min_contributing_sources': 2,
                'min_relevant_at_10': 1, 'min_recall_percent_at_10': 100,
                'max_missing_image_media': 0,
                'require_all_sources_healthy': True,
            },
        }
        result = quality.evaluate_fixture(fixture)
        self.assertTrue(result['passed'])
        self.assertEqual(1, result['distinct_results'])
        self.assertEqual(2, result['collapsed_duplicates'])
        self.assertEqual(2, result['contributing_sources'])

    def test_supports_only_current_fusion_categories(self):
        for category in ('web', 'images', 'videos', 'news'):
            fixture = images()
            fixture['category'] = category
            if category != 'images':
                fixture['relevant'] = [
                    'https://example.test/album/1',
                    'https://example.test/other/2',
                ]
                fixture['gates']['min_distinct'] = 4
                fixture['gates']['min_relevant_at_10'] = 2
            with self.subTest(category=category):
                self.assertTrue(quality.evaluate_fixture(fixture)['passed'])
        for category in ('maps', 'shopping', 'more'):
            fixture = images()
            fixture['category'] = category
            with self.subTest(category=category), self.assertRaises(
                    quality.InvalidBenchmark):
                quality.evaluate_fixture(fixture)

    def test_strict_contract_rejects_raw_query_and_bad_provider_evidence(self):
        fixture = images()
        variants = []
        bad = deepcopy(fixture)
        bad['q'] = 'personal query must not persist'
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['sources'][0]['source'] = 'source with secret: ...'
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['sources'][0]['results'][0]['raw_html'] = 'sensitive'
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['sources'][0]['results'][0]['url'] = 'file:///private'
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['sources'][0]['results'][0]['rank'] = True
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['sources'][0]['state'] = 'access_denied'
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['sources'][0]['results'][0]['media_url'] = 'http://user:pass@example.test/asset'
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['sources'][0]['source'] = fixture['sources'][1]['source']
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['relevant'][1] = bad['relevant'][0]
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['gates']['min_recall_percent_at_10'] = 101
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['gates']['require_all_sources_healthy'] = 1
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['gates']['min_sources_with_unique_at_10'] = 13
        variants.append(bad)
        bad = deepcopy(fixture)
        bad['gates']['min_sources_with_unique_at_10'] = 3
        variants.append(bad)
        for index, doc in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(
                    quality.InvalidBenchmark):
                quality.evaluate_fixture(doc)

    def test_bounded_candidates_and_fixture_size(self):
        fixture = images()
        fixture['sources'][0]['results'] *= 40
        with self.assertRaises(quality.InvalidBenchmark):
            quality.evaluate_fixture(fixture)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.json'
            path.write_text(' ' * (quality.MAX_FIXTURE_BYTES + 1), encoding='utf-8')
            sink = StringIO()
            with contextlib.redirect_stdout(sink):
                self.assertEqual(2, quality.main([str(path)]))
            self.assertEqual('fixture_oversized', json.loads(sink.getvalue())['reason'])

    def test_cli_validates_offline_fixture_without_echoing_input_paths_or_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.json'
            path.write_text(json.dumps(images()), encoding='utf-8')
            sink = StringIO()
            with contextlib.redirect_stdout(sink), patch(
                    'socket.create_connection', side_effect=AssertionError('network forbidden')):
                self.assertEqual(0, quality.main([str(path)]))
            response = json.loads(sink.getvalue())
            self.assertEqual('pass', response['state'])
            self.assertFalse(response['release_qualified'])
            self.assertNotIn(directory, sink.getvalue())
            self.assertNotIn('https://', sink.getvalue())
            fixture = images()
            fixture['raw_query'] = 'very private search'
            path.write_text(json.dumps(fixture), encoding='utf-8')
            sink = StringIO()
            with contextlib.redirect_stdout(sink):
                self.assertEqual(2, quality.main([str(path)]))
            self.assertNotIn('private search', sink.getvalue())
            self.assertNotIn(directory, sink.getvalue())

    def test_cli_without_fixture_never_contacts_provider(self):
        sink = StringIO()
        with contextlib.redirect_stdout(sink):
            self.assertEqual(64, quality.main([]))
        self.assertIn('No provider requests', sink.getvalue())


if __name__ == '__main__':
    unittest.main()
