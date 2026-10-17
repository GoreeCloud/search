"""No-provider regression: explicit source changes preserve search intent and filters."""
import unittest
from unittest.mock import patch
from lxml import html
import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch


class ProviderSwitchFilterTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_switch_forms_keep_filters_and_request_only_approved_sources(self):
        terms = 'synthetic <offline> & "query"'
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            response = client.post('/search', data={
                'q': terms, 'engines': 'brave,startpage', 'category_general': '1',
                'language': 'en', 'safesearch': '2', 'time_range': 'week',
                'theme': 'simple', 'timeout_limit': '2.75',
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertNotIn('Set-Cookie', response.headers)
            page = html.fromstring(response.data)
            forms = page.xpath('//section[contains(@class,"goreecloud-source-switch")]//form')
            self.assertEqual(3, len(forms))
            for form, source in zip(forms, ('brave,startpage', 'brave', 'startpage')):
                with self.subTest(source=source):
                    self.assertEqual('post', form.get('method'))
                    self.assertEqual('/search', form.get('action'))
                    values = {node.get('name'): node.get('value') for node in form.xpath('.//input')}
                    expected = {'q': terms, 'engines': source, 'category_general': '1',
                                'language': 'en', 'safesearch': '2', 'time_range': 'week',
                                'theme': 'simple', 'timeout_limit': '2.75'}
                    self.assertEqual(expected, values)
                    self.assertNotIn('q=', form.get('action'))
                    next_page = client.post('/search', data={**values, 'format':'json'}, headers=self.headers)
                    self.assertEqual(200, next_page.status_code)
                    self.assertEqual(sorted(source.split(',')), next_page.json['goreecloud']['selected_engines'])
                    self.assertNotIn('Location', next_page.headers)
                    next_page.close()
            response.close()

    def test_source_only_normalizes_bang_rather_than_overriding_selected_engine(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            result = client.post('/search', data={'q':'!sp synthetic terms'}, headers=self.headers)
            self.assertEqual(200, result.status_code)
            doc = html.fromstring(result.data)
            forms = doc.xpath('//form[contains(@class,"goreecloud-refine-source")]')
            self.assertEqual(1, len(forms))
            form = forms[0]
            self.assertEqual('post', form.get('method'))
            self.assertEqual(['synthetic terms'], form.xpath('.//input[@name="q"]/@value'))
            self.assertEqual(['startpage'], form.xpath('.//input[@name="engines"]/@value'))
            result.close()
