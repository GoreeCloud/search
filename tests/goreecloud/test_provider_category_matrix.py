"""Offline end-to-end category/source selection for GoreeCloud Search.

A correct registry is not enough: assert that the private POST endpoint
actually selects each of the 24 approved category adapters and never silently
substitutes an unsupported provider. Fake search dispatch means no egress.
"""
import unittest
from unittest.mock import patch

import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch
from searx.goreecloud_policy import SEARCH_SOURCE_FAMILIES


class PrivateCategorySelectionMatrixTests(unittest.TestCase):
    HEADERS = {'X-Real-IP': '127.0.0.1'}

    @staticmethod
    def form(category, engine):
        values = {'q': 'goreecloud offline category test',
                  'engines': engine, 'format': 'json'}
        if category != 'general':
            values['category_' + category] = '1'
        return values

    def test_all_24_approved_adapters_select_exactly_requested_source(self):
        expected = {'general': 7, 'images': 6, 'videos': 5, 'news': 6}
        self.assertEqual(expected, {
            name: len(engines) for name, engines in SEARCH_SOURCE_FAMILIES.items()
        })
        with smoke.app.test_client() as client, patch(
            'searx.search.SearchWithPlugins', side_effect=OfflineSearch
        ) as search_factory:
            for category, mapping in SEARCH_SOURCE_FAMILIES.items():
                for family, adapter in mapping.items():
                    with self.subTest(category=category, family=family):
                        response = client.post('/search', data=self.form(category, adapter),
                                               headers=self.HEADERS)
                        self.assertEqual(200, response.status_code)
                        self.assertTrue(response.is_json)
                        self.assertEqual(
                            [adapter], response.json['goreecloud']['selected_engines']
                        )
                        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
                        self.assertEqual('no-referrer', response.headers.get('Referrer-Policy'))
                        self.assertNotIn('Location', response.headers)
                        response.close()
            self.assertEqual(sum(expected.values()), search_factory.call_count)

    def test_unsupported_and_cross_category_adapters_fail_without_search(self):
        prohibited = (
            ('images', 'ecosia'),
            ('videos', 'startpage'),
            ('videos', 'ecosia'),
            ('news', 'ecosia'),
            ('images', 'brave.images,bing news'),
        )
        with smoke.app.test_client() as client, patch(
            'searx.search.SearchWithPlugins', side_effect=OfflineSearch
        ) as search_factory:
            for category, adapter in prohibited:
                with self.subTest(category=category, adapter=adapter):
                    response = client.post('/search', data=self.form(category, adapter),
                                           headers=self.HEADERS)
                    self.assertEqual(422, response.status_code)
                    self.assertIn('no-store', response.headers.get('Cache-Control', ''))
                    response.close()
            search_factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
