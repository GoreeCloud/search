"""Explicit, privacy-preserving provider recovery regression tests."""
import unittest
from unittest.mock import patch
from lxml import html

import test_runtime_smoke as smoke
from test_empty_results_recovery import FailedSourceSearch
from test_search_preview import OfflineSearch


class StartpageRecoveryTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def _search(self, data, mock=FailedSourceSearch):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', mock):
            response = client.post('/search', data=data, headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertNotIn('Location', response.headers)
            parsed = html.fromstring(response.data)
            forms = parsed.xpath('//form[contains(@class, "goreecloud-try-startpage")]')
            return response, forms

    def test_explicit_recovery_preserves_query_filters_and_post_only(self):
        for category, names, only in (
            ('general', 'brave,startpage,qwant,duckduckgo,ecosia,bing,google', 'startpage'),
            ('images', 'brave.images,startpage images,qwant images,duckduckgo images,bing images,google images', 'startpage images'),
            ('news', 'brave.news,startpage news,qwant news,duckduckgo news,bing news,google news', 'startpage news'),
        ):
            with self.subTest(category=category):
                data = {'q': 'synthetic <private> & "terms"',
                        'engines': names, 'category_' + category: '1',
                        'language': 'en', 'time_range': 'week', 'safesearch': '2'}
                response, forms = self._search(data)
                self.assertEqual(1, len(forms))
                form = forms[0]
                self.assertEqual('post', form.get('method'))
                self.assertEqual('/search', form.get('action'))
                fields = {x.get('name'): x.get('value') for x in form.xpath('.//input')}
                self.assertEqual(data['q'], fields['q'])
                self.assertEqual(only, fields['engines'])
                self.assertEqual('1', fields['category_' + category])
                for key in ('language', 'time_range', 'safesearch'):
                    self.assertEqual(data[key], fields[key])
                self.assertNotIn('q=', form.get('action'))
                self.assertNotIn('preferences', fields)
                self.assertNotIn('Set-Cookie', response.headers)
                self.assertIn('saved provider preferences do not change', response.get_data(as_text=True))
                response.close()

    def test_no_auto_recovery_for_unselected_or_already_single_source(self):
        for engines, category in (
            ('brave,qwant', 'general'),
            ('brave', 'general'),
            ('startpage', 'general'),
            ('qwant images,brave.images', 'images'),
            ('brave.videos,qwant videos,duckduckgo videos,bing videos,google videos', 'videos'),
        ):
            with self.subTest(engines=engines):
                response, forms = self._search({
                    'q': 'synthetic', 'engines': engines,
                    'category_' + category: '1',
                })
                self.assertFalse(forms)
                response.close()

    def test_no_recovery_without_provider_errors(self):
        response, forms = self._search({
            'q': 'synthetic', 'engines': 'brave,startpage,qwant,duckduckgo,ecosia,bing,google',
        }, mock=OfflineSearch)
        self.assertFalse(forms)
        response.close()


if __name__ == '__main__':
    unittest.main()
