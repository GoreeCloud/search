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


class SyntheticTimedPopulatedSearch(SyntheticPopulatedSearch):
    def search(self):
        response = super().search()
        response.get_timings = lambda: [SimpleNamespace(engine='brave', total=0.38, load=0.12)]
        return response


class SyntheticTimedPartialFailure(SyntheticTimedPopulatedSearch):
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

    def test_source_messages_expand_only_when_timed_results_include_provider_errors(self):
        for provider_cls, expanded in (
            (SyntheticTimedPopulatedSearch, False),
            (SyntheticTimedPartialFailure, True),
        ):
            with self.subTest(provider_errors=expanded), smoke.app.test_client() as client, patch(
                'searx.search.SearchWithPlugins', provider_cls
            ):
                response = client.post('/search', data={
                    'q': 'synthetic source message status', 'engines': 'brave,startpage',
                }, headers=self.headers)
                self.assertEqual(200, response.status_code)
                doc = html.fromstring(response.data)
                panels = doc.xpath('//div[@id="engines_msg"]/details')
                self.assertEqual(1, len(panels))
                self.assertEqual(expanded, panels[0].get('open') is not None)
                messages = panels[0].xpath('.//td[contains(@class,"response-error")]')
                self.assertEqual(int(expanded), len(messages))
                self.assertEqual(expanded, bool(doc.xpath('//p[contains(@class,"goreecloud-partial-results")]')))
                self.assertIn('no-store', response.headers['Cache-Control'])
                response.close()

    def test_partial_failure_retry_replays_only_selected_sources(self):
        cases = (
            (
                {'q': 'synthetic <offline> & "private"', 'engines': 'brave,startpage',
                 'category_general': '1', 'language': 'en', 'time_range': 'week',
                 'safesearch': '2', 'theme': 'simple', 'timeout_limit': '2.75',
                 'pageno': '2'},
                'brave,startpage', 'synthetic <offline> & "private"', '2',
            ),
            (
                {'q': '!sp synthetic partial failure', 'language': 'en',
                 'theme': 'simple'},
                'startpage', 'synthetic partial failure', '1',
            ),
        )
        for request_fields, expected_sources, expected_query, expected_page in cases:
            with self.subTest(sources=expected_sources), smoke.app.test_client() as client, patch(
                'searx.search.SearchWithPlugins', SyntheticTimedPartialFailure
            ):
                response = client.post('/search', data=request_fields, headers=self.headers)
                self.assertEqual(200, response.status_code)
                doc = html.fromstring(response.data)
                self.assertEqual(1, len(doc.xpath('//p[contains(@class,"goreecloud-partial-results")][@role="status"]')))
                forms = doc.xpath('//form[contains(@class,"goreecloud-partial-retry")]')
                self.assertEqual(1, len(forms))
                form = forms[0]
                self.assertEqual('post', form.get('method').lower())
                self.assertEqual('/search', form.get('action'))
                self.assertEqual(['Retry selected sources'], [
                    ' '.join(node.text_content().split()) for node in form.xpath('./button')
                ])
                fields = {node.get('name'): node.get('value') for node in form.xpath('.//input')}
                self.assertEqual(expected_query, fields['q'])
                self.assertEqual(expected_sources, fields['engines'])
                self.assertEqual(expected_page, fields['pageno'])
                self.assertNotIn('format', fields)
                self.assertNotIn('q=', form.get('action'))
                for key in ('language', 'time_range', 'safesearch', 'theme', 'timeout_limit'):
                    if key in request_fields:
                        self.assertEqual(request_fields[key], fields[key])
                # Compare parsed categories with the authoritative source-refine form.
                refine = doc.xpath('//form[contains(@class,"goreecloud-refine-source")]')[0]
                refined = {e.get('name'): e.get('value') for e in refine.xpath('.//input')
                           if e.get('name', '').startswith('category_')}
                retried = {k: v for k, v in fields.items() if k.startswith('category_')}
                self.assertEqual(refined, retried)
                self.assertIn('no-store', response.headers['Cache-Control'])
                self.assertEqual('no-referrer', response.headers['Referrer-Policy'])
                self.assertNotIn('Location', response.headers)
                response.close()

                with patch('searx.search.SearchWithPlugins', OfflineSearch):
                    replay = client.post('/search', data={**fields, 'format': 'json'},
                                         headers=self.headers)
                    self.assertEqual(200, replay.status_code)
                    self.assertEqual(sorted(expected_sources.split(',')),
                                     replay.json['goreecloud']['selected_engines'])
                    self.assertEqual(expected_query, replay.json['query'])
                    self.assertNotIn('Location', replay.headers)
                    replay.close()

    def test_partial_retry_absent_when_no_provider_error(self):
        with smoke.app.test_client() as client, patch(
            'searx.search.SearchWithPlugins', SyntheticTimedPopulatedSearch
        ):
            response = client.post('/search', data={
                'q': 'synthetic healthy sources', 'engines': 'brave,startpage',
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            doc = html.fromstring(response.data)
            self.assertFalse(doc.xpath('//form[contains(@class,"goreecloud-partial-retry")]'))
            self.assertFalse(doc.xpath('//p[contains(@class,"goreecloud-partial-results")]'))
            response.close()
