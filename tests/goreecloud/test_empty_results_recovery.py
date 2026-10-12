"""Private no-results and explicit retry behavior, exercised without network egress."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lxml import html
import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch


class FailedSourceSearch(OfflineSearch):
    def search(self):
        response = super().search()
        response.unresponsive_engines = [
            SimpleNamespace(engine='startpage', error_type='TimeoutException', suspended=False)
        ]
        return response


class PrivateEmptyResultsTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_failure_explains_uncertainty_and_offers_explicit_same_source_retry(self):
        terms = 'test <offline> & "query"'
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', FailedSourceSearch):
            result = client.post('/search', data={
                'q': terms, 'engines': 'startpage', 'language': 'en',
                'safesearch': '2', 'time_range': 'week',
            }, headers=self.headers)
            self.assertEqual(200, result.status_code)
            self.assertIn('no-store', result.headers['Cache-Control'])
            self.assertEqual('no-referrer', result.headers['Referrer-Policy'])
            self.assertNotIn('Location', result.headers)
            page = html.fromstring(result.data)
            state = page.xpath('//section[contains(@class,"goreecloud-empty-state")]')[0]
            self.assertEqual('Search results unavailable', ' '.join(state.xpath('.//h2')[0].text_content().split()))
            self.assertIn('reported an error', state.text_content())
            self.assertIn('No replacement provider was selected automatically.', state.text_content())
            retry = state.xpath('.//form[contains(@class,"goreecloud-empty-retry")]')
            self.assertEqual(1, len(retry))
            self.assertEqual('post', retry[0].get('method'))
            self.assertEqual('/search', retry[0].get('action'))
            self.assertEqual('Retry selected sources', retry[0].xpath('.//button')[0].text_content().strip())
            fields = {field.get('name'): field.get('value') for field in retry[0].xpath('.//input')}
            self.assertEqual(terms, fields['q'])
            self.assertEqual('startpage', fields['engines'])
            self.assertEqual('en', fields['language'])
            self.assertEqual('2', fields['safesearch'])
            self.assertEqual('week', fields['time_range'])
            self.assertNotIn('format', fields)
            self.assertNotIn('q=', retry[0].get('action'))
            result.close()

            with patch('searx.search.SearchWithPlugins', OfflineSearch):
                again = client.post('/search', data={**fields, 'format':'json'}, headers=self.headers)
                self.assertEqual(200, again.status_code)
                self.assertEqual(['startpage'], again.json['goreecloud']['selected_engines'])
                self.assertNotIn('Location', again.headers)
                again.close()

    def test_no_provider_error_does_not_offer_retry_or_invent_an_outage(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            result = client.post('/search', data={'q': 'offline no results', 'engines': 'brave'},
                                 headers=self.headers)
            self.assertEqual(200, result.status_code)
            page = html.fromstring(result.data)
            self.assertFalse(page.xpath('//form[contains(@class,"goreecloud-empty-retry")]'))
            state = page.xpath('//section[contains(@class,"goreecloud-empty-state")]')[0]
            self.assertIn('No results found', state.text_content())
            self.assertNotIn('reported an error', state.text_content())
            self.assertIn('Brave Search and Startpage', state.text_content())
            result.close()

    def test_multi_source_error_retry_keeps_both_without_fallback(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', FailedSourceSearch):
            result = client.post('/search', data={'q': 'offline two source', 'engines': 'brave,startpage'},
                                 headers=self.headers)
            self.assertEqual(200, result.status_code)
            page = html.fromstring(result.data)
            retry = page.xpath('//form[contains(@class,"goreecloud-empty-retry")]')
            self.assertEqual(1, len(retry))
            self.assertEqual('brave,startpage', retry[0].xpath('.//input[@name="engines"]/@value')[0])
            self.assertNotIn('q=', retry[0].get('action'))
            result.close()
