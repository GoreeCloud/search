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
            self.assertIn('choose a different approved source in Settings', state.text_content())
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

    def test_later_empty_page_offers_private_post_to_previous_page(self):
        scenarios = (
            (
                {'q': 'synthetic <offline> & "query"', 'engines': 'brave,startpage',
                 'pageno': '3', 'category_general': '1', 'language': 'en',
                 'safesearch': '2', 'time_range': 'week', 'theme': 'simple',
                 'timeout_limit': '2.75'},
                'brave,startpage', 'synthetic <offline> & "query"', '2',
            ),
            (
                {'q': '!sp synthetic previous query', 'pageno': '2'},
                'startpage', 'synthetic previous query', '1',
            ),
        )
        for request_fields, providers, query, previous_page in scenarios:
            with self.subTest(providers=providers, page=previous_page), smoke.app.test_client() as client, patch(
                'searx.search.SearchWithPlugins', OfflineSearch
            ):
                response = client.post('/search', data=request_fields, headers=self.headers)
                self.assertEqual(200, response.status_code)
                doc = html.fromstring(response.data)
                sections = doc.xpath('//section[contains(@class,"goreecloud-empty-state")]')
                self.assertEqual(1, len(sections))
                self.assertIn('No more results', sections[0].text_content())
                self.assertFalse(doc.xpath('//form[contains(@class,"goreecloud-empty-retry") and not(contains(@class,"goreecloud-previous-results"))]'))
                previous = sections[0].xpath('./form[contains(@class,"goreecloud-previous-results")]')
                self.assertEqual(1, len(previous))
                form = previous[0]
                self.assertEqual('post', form.get('method').lower())
                self.assertEqual('/search', form.get('action'))
                self.assertEqual('Previous results page', form.xpath('./button')[0].text_content().strip())
                fields = {e.get('name'): e.get('value') for e in form.xpath('.//input')}
                self.assertEqual(query, fields['q'])
                self.assertEqual(providers, fields['engines'])
                self.assertEqual(previous_page, fields['pageno'])
                self.assertNotIn('q=', form.get('action'))
                self.assertNotIn('format', fields)
                self.assertIn('no-store', response.headers['Cache-Control'])
                self.assertEqual('no-referrer', response.headers['Referrer-Policy'])
                self.assertNotIn('Location', response.headers)
                for key in ('language', 'safesearch', 'time_range', 'theme', 'timeout_limit'):
                    if key in request_fields:
                        self.assertEqual(request_fields[key], fields[key])
                expected_categories = {k:v for k,v in request_fields.items() if k.startswith('category_')}
                if request_fields['q'].startswith('!sp '):
                    expected_categories['category_none'] = '1'
                actual_categories = {k: v for k, v in fields.items() if k.startswith('category_')}
                self.assertEqual(expected_categories, actual_categories)
                response.close()

                repeated = client.post('/search', data={**fields, 'format': 'json'},
                                       headers=self.headers)
                self.assertEqual(200, repeated.status_code)
                self.assertEqual(sorted(providers.split(',')),
                                 repeated.json['goreecloud']['selected_engines'])
                self.assertEqual(query, repeated.json['query'])
                self.assertNotIn('Location', repeated.headers)
                repeated.close()

    def test_first_empty_page_does_not_offer_previous_page(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            result = client.post('/search', data={'q': 'first page', 'engines': 'brave', 'pageno': '1'},
                                 headers=self.headers)
            self.assertEqual(200, result.status_code)
            doc = html.fromstring(result.data)
            self.assertFalse(doc.xpath('//form[contains(@class,"goreecloud-previous-results")]'))
            result.close()

    def test_later_page_errors_show_uncertainty_and_two_explicit_actions(self):
        scenarios = (
            ({'q': 'synthetic <private> & "terms"', 'engines': 'brave,startpage',
              'pageno': '3', 'category_general': '1', 'language': 'en',
              'safesearch': '2', 'time_range': 'week', 'theme': 'simple',
              'timeout_limit': '2.75'},
             'brave,startpage', 'synthetic <private> & "terms"', '3', '2'),
            ({'q': '!sp synthetic later error', 'pageno': '2'},
             'startpage', 'synthetic later error', '2', '1'),
        )
        for submitted, selected, terms, current, previous in scenarios:
            with self.subTest(provider=selected), smoke.app.test_client() as client, patch(
                'searx.search.SearchWithPlugins', FailedSourceSearch
            ):
                response = client.post('/search', data=submitted, headers=self.headers)
                self.assertEqual(200, response.status_code)
                doc = html.fromstring(response.data)
                area = doc.xpath('//section[contains(@class, "goreecloud-empty-state")]')[0]
                self.assertEqual('Search results unavailable',
                                 ' '.join(area.xpath('./h2')[0].text_content().split()))
                self.assertIn('results for this page could not be confirmed', area.text_content())
                self.assertNotIn('No more displayed web matches', area.text_content())
                self.assertIn('No replacement provider was selected automatically', area.text_content())
                self.assertEqual(['#engines_msg-title'], area.xpath('./p/a/@href'))
                self.assertIsNotNone(doc.xpath('//div[@id="engines_msg"]/details')[0].get('open'))
                self.assertIn('no-store', response.headers['Cache-Control'])
                self.assertEqual('no-referrer', response.headers['Referrer-Policy'])
                self.assertNotIn('Set-Cookie', response.headers)
                self.assertNotIn('Location', response.headers)
                categories = {k:v for k,v in submitted.items() if k.startswith('category_')}
                if submitted['q'].startswith('!sp '):
                    categories['category_none'] = '1'
                for selector, page_no, button in (
                    ('goreecloud-page-error-retry', current, 'Retry this results page'),
                    ('goreecloud-previous-results', previous, 'Previous results page'),
                ):
                    with self.subTest(action=selector):
                        form = area.xpath('./form[contains(@class, "' + selector + '")]')
                        self.assertEqual(1, len(form))
                        self.assertEqual('post', form[0].get('method').lower())
                        self.assertEqual('/search', form[0].get('action'))
                        self.assertEqual(button, form[0].xpath('./button')[0].text_content().strip())
                        fields = {e.get('name'): e.get('value') for e in form[0].xpath('.//input')}
                        self.assertEqual(terms, fields['q'])
                        self.assertEqual(selected, fields['engines'])
                        self.assertEqual(page_no, fields['pageno'])
                        self.assertNotIn('format', fields)
                        self.assertNotIn('q=', form[0].get('action'))
                        self.assertEqual(categories, {k: v for k, v in fields.items()
                                                      if k.startswith('category_')})
                        for key in ('language', 'safesearch', 'time_range', 'theme', 'timeout_limit'):
                            if key in submitted:
                                self.assertEqual(submitted[key], fields[key])
                        with patch('searx.search.SearchWithPlugins', OfflineSearch):
                            replay = client.post('/search', data={**fields, 'format': 'json'},
                                                 headers=self.headers)
                            self.assertEqual(200, replay.status_code)
                            self.assertEqual(sorted(selected.split(',')),
                                             replay.json['goreecloud']['selected_engines'])
                            self.assertEqual(terms, replay.json['query'])
                            self.assertNotIn('Location', replay.headers)
                            replay.close()
                response.close()

    def test_later_page_without_error_remains_exhausted_not_failed(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            response = client.post('/search', data={'q': 'synthetic exhausted',
                'engines': 'brave', 'pageno': '3'}, headers=self.headers)
            self.assertEqual(200, response.status_code)
            doc = html.fromstring(response.data)
            area = doc.xpath('//section[contains(@class, "goreecloud-empty-state")]')[0]
            self.assertEqual('No more results', area.xpath('./h2')[0].text_content().strip())
            self.assertFalse(area.xpath('./form[contains(@class, "goreecloud-page-error-retry")]'))
            self.assertEqual(1, len(area.xpath('./form[contains(@class, "goreecloud-previous-results")]')))
            self.assertNotIn('reported an error', area.text_content())
            response.close()
