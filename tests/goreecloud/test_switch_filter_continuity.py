"""No-provider regression: explicit source changes preserve search intent and filters."""
import unittest
from unittest.mock import patch
from lxml import html
import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch


class ProviderSwitchFilterTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_post_source_selection_keeps_filters_and_approved_engines(self):
        terms = 'synthetic <offline> & "query"'
        headers = self.headers
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            for source in ('brave,startpage', 'brave', 'startpage'):
                with self.subTest(source=source):
                    data = {'q': terms, 'engines': source, 'category_general': '1',
                            'language': 'en', 'safesearch': '2', 'time_range': 'week',
                            'theme': 'simple', 'timeout_limit': '2.75', 'format': 'json'}
                    response = client.post('/search', data=data, headers=headers)
                    self.assertEqual(200, response.status_code)
                    self.assertEqual(sorted(source.split(',')), response.json['goreecloud']['selected_engines'])
                    self.assertEqual(terms, response.json['query'])
                    self.assertNotIn('Location', response.headers)
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    response.close()
            home = client.get('/', headers=headers)
            self.assertFalse(html.fromstring(home.data).xpath('//button[contains(@class,"goreecloud-home-source")]'))
            home.close()

    def test_bang_normalizes_to_approved_source_without_result_switches(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            response = client.post('/search', data={'q':'!sp synthetic terms', 'format':'json'}, headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertEqual('synthetic terms', response.json['query'])
            self.assertEqual(['startpage'], response.json['goreecloud']['selected_engines'])
            response.close()
            page = client.post('/search', data={'q':'!sp synthetic terms'}, headers=self.headers)
            self.assertEqual(200, page.status_code)
            self.assertFalse(html.fromstring(page.data).xpath('//form[contains(@class,"goreecloud-refine-source")]'))
            page.close()
