"""Provider partial-results warning and query-bound input hints; offline-only tests."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lxml import html

import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch
from searx.result_types import LegacyResult


class SyntheticPopulatedSearch(OfflineSearch):
    errors = False

    def search(self):
        item = LegacyResult(
            url='https://example.org/synthetic-item',
            title='Synthetic offline result',
            content='Fixture only; no provider was contacted',
        )
        item.normalize_result_fields()
        response = super().search()
        response.get_ordered_results = lambda: [item]
        response.unresponsive_engines = (
            [SimpleNamespace(engine='startpage', error_type='TimeoutException', suspended=False)]
            if self.errors else []
        )
        return response


class SyntheticPartialFailure(SyntheticPopulatedSearch):
    errors = True


class PartialResultsAndLengthTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_populated_results_disclose_reported_provider_error(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', SyntheticPartialFailure):
            response = client.post('/search', data={
                'q': 'synthetic partial result', 'engines': 'brave,startpage',
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            doc = html.fromstring(response.data)
            notices = doc.xpath('//p[contains(@class,"goreecloud-partial-results")][@role="status"]')
            self.assertEqual(1, len(notices))
            self.assertIn('Displayed results may be incomplete.', notices[0].text_content())
            self.assertIn('No replacement provider is selected automatically.', notices[0].text_content())
            self.assertEqual(['#engines_msg-title'], notices[0].xpath('.//a/@href'))
            self.assertFalse(doc.xpath('//section[contains(@class,"goreecloud-empty-state")]'))
            self.assertIn('Synthetic offline result', doc.text_content())
            self.assertIn('2 source(s) selected', doc.text_content())
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertNotIn('Location', response.headers)
            response.close()

    def test_successful_populated_result_has_no_partial_failure_claim(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', SyntheticPopulatedSearch):
            response = client.post('/search', data={
                'q': 'synthetic normal result', 'engines': 'brave',
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            doc = html.fromstring(response.data)
            self.assertFalse(doc.xpath('//p[contains(@class,"goreecloud-partial-results")]'))
            self.assertIn('Synthetic offline result', doc.text_content())
            response.close()

    def test_both_private_query_inputs_expose_server_limit(self):
        with smoke.app.test_client() as client:
            home = client.get('/', headers=self.headers)
            self.assertEqual(200, home.status_code)
            home_doc = html.fromstring(home.data)
            self._assert_bounded_input(home_doc)
            home.close()
            with patch('searx.search.SearchWithPlugins', OfflineSearch):
                results = client.post('/search', data={'q': 'offline', 'engines': 'startpage'},
                                      headers=self.headers)
                self.assertEqual(200, results.status_code)
                result_doc = html.fromstring(results.data)
                self._assert_bounded_input(result_doc)
                results.close()

    def test_direct_post_over_limit_is_still_rejected_by_server(self):
        marker = 'sensitive-private-marker-' + ('x' * 513)
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as executor:
            response = client.post('/search', data={'q': marker, 'format': 'json'},
                                   headers=self.headers)
            self.assertEqual(413, response.status_code)
            self.assertNotIn(marker, response.get_data(as_text=True))
            self.assertIn('no-store', response.headers['Cache-Control'])
            executor.assert_not_called()
            response.close()

    def _assert_bounded_input(self, doc):
        q = doc.xpath('//form[@id="search"]//input[@name="q"]')
        self.assertEqual(1, len(q))
        self.assertEqual('512', q[0].get('maxlength'))
        self.assertEqual('goreecloud-query-length-hint', q[0].get('aria-describedby'))
        hints = doc.xpath('//*[@id="goreecloud-query-length-hint"]')
        self.assertEqual(1, len(hints))
        self.assertIn('512 characters', hints[0].text_content())
