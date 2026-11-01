"""Offline regression checks for a single provider repeating one Web result.

All URLs and engine names are synthetic; no provider is contacted.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import searx.engines
from searx.result_types import MainResult
from searx.results import ResultContainer


class WebResultVoteDedupTests(unittest.TestCase):
    def setUp(self):
        self.engines = {
            name: SimpleNamespace(name=name, weight=1.0, paging=False, categories=['general'])
            for name in ('synthetic-alpha', 'synthetic-beta')
        }
        self.engines_patch = patch.dict(searx.engines.engines, self.engines)
        self.histogram_patch = patch('searx.results.histogram_observe')
        self.counter_patch = patch('searx.results.counter_add')
        self.engines_patch.start()
        self.histogram_patch.start()
        self.counter_patch.start()
        self.addCleanup(self.engines_patch.stop)
        self.addCleanup(self.histogram_patch.stop)
        self.addCleanup(self.counter_patch.stop)

    def test_same_provider_repetition_does_not_inflate_web_rank(self):
        url = 'https://example.invalid/one'
        container = ResultContainer()
        container.extend('synthetic-alpha', [
            {'url': url, 'title': 'Original', 'content': 'Brief snippet'},
            {'url': url, 'title': 'Original', 'content': 'A more useful expanded snippet'},
            {'url': url, 'title': 'Original', 'content': 'Brief snippet'},
        ])
        container.close()

        self.assertEqual(1, len(container.main_results_map))
        result = next(iter(container.main_results_map.values()))
        self.assertEqual({'synthetic-alpha'}, result.engines)
        self.assertEqual([1], result.positions)
        self.assertEqual(1.0, result.score)
        self.assertEqual('A more useful expanded snippet', result.content)

    def test_two_independent_sources_still_both_count_once(self):
        url = 'https://example.invalid/two'
        container = ResultContainer()
        container.extend('synthetic-alpha', [MainResult(url=url, title='First')])
        container.extend('synthetic-beta', [{'url': 'http://example.invalid/two', 'title': 'Second'}])
        container.extend('synthetic-alpha', [MainResult(url=url, title='First repeated')])
        container.close()

        self.assertEqual(1, len(container.main_results_map))
        result = next(iter(container.main_results_map.values()))
        self.assertEqual({'synthetic-alpha', 'synthetic-beta'}, result.engines)
        self.assertEqual([1, 1], result.positions)
        self.assertEqual(4.0, result.score)

    def test_duplicate_storm_cannot_outscore_an_independent_web_result(self):
        container = ResultContainer()
        duplicate = {'url': 'https://example.invalid/repeated', 'title': 'Repeated'}
        container.extend('synthetic-alpha', [duplicate.copy() for _ in range(128)])
        container.extend('synthetic-beta', [
            {'url': 'https://example.invalid/independent', 'title': 'Independent'}
        ])
        container.close()

        by_title = {result.title: result for result in container.main_results_map.values()}
        self.assertEqual(2, len(by_title))
        self.assertEqual([1], by_title['Repeated'].positions)
        self.assertEqual(by_title['Independent'].score, by_title['Repeated'].score)

    def test_distinct_web_documents_are_not_collapsed(self):
        container = ResultContainer()
        container.extend('synthetic-alpha', [
            {'url': 'https://example.invalid/page#section-a', 'title': 'Section A'},
            {'url': 'https://example.invalid/page#section-b', 'title': 'Section B'},
        ])
        container.close()

        self.assertEqual(2, len(container.main_results_map))
        self.assertEqual([[1], [2]], [item.positions for item in container.main_results_map.values()])

    def test_non_web_result_scoring_is_unchanged(self):
        image = {
            'url': 'https://example.invalid/image-page',
            'img_src': 'https://example.invalid/pixel.png',
            'template': 'images.html',
            'title': 'Synthetic image',
        }
        container = ResultContainer()
        container.extend('synthetic-alpha', [image.copy(), image.copy()])
        container.close()

        self.assertEqual([1, 2], next(iter(container.main_results_map.values())).positions)


if __name__ == '__main__':
    unittest.main()
