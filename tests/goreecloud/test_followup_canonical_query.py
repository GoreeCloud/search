"""Guard original private query against stateful suggestion/correction rewrites.

All providers are synthetic. This protects every private navigation form from
accidentally executing the last correction instead of the original search.
"""
import unittest
from unittest.mock import patch

from lxml import html

import test_runtime_smoke as smoke
from test_source_continuity import PagedSearch
from test_empty_results_recovery import FailedSourceSearch


SUGGESTED = 'different suggested <offline> words'
CORRECTED = 'different corrected & "words"'


class SuggestedPagedSearch(PagedSearch):
    def search(self):
        response = super().search()
        response.suggestions = [SUGGESTED]
        response.corrections = [CORRECTED]
        return response


class SuggestedFailedSearch(FailedSourceSearch):
    def search(self):
        response = super().search()
        response.suggestions = [SUGGESTED]
        response.corrections = [CORRECTED]
        return response


class CanonicalPrivateQueryTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    @staticmethod
    def fields(form):
        return {el.get('name'): el.get('value') for el in form.xpath('.//input[@name]')}

    def assert_private_form(self, form, terms, providers, page=None):
        self.assertEqual('post', form.get('method').lower())
        self.assertEqual('/search', form.get('action'))
        fields = self.fields(form)
        self.assertEqual(terms, fields['q'])
        self.assertEqual(providers, fields['engines'])
        self.assertNotIn('q=', form.get('action'))
        if page is not None:
            self.assertEqual(page, fields['pageno'])
        self.assertNotIn(SUGGESTED, fields['q'])
        self.assertNotIn(CORRECTED, fields['q'])
        return fields

    def test_populated_results_keep_original_terms_in_switch_refine_and_pagination(self):
        cases = (
            ('!sp original <offline> & "terms"', 'original <offline> & "terms"', 'startpage'),
            ('original <offline> & "terms"', 'original <offline> & "terms"', 'brave,startpage'),
        )
        for original, terms, selected in cases:
            with self.subTest(selected=selected), smoke.app.test_client() as client, patch(
                'searx.search.SearchWithPlugins', SuggestedPagedSearch
            ):
                response = client.post('/search', data={
                    'q': original, 'pageno': '2',
                    **({} if original.startswith('!sp') else {'engines': selected}),
                }, headers=self.headers)
                self.assertEqual(200, response.status_code)
                document = html.fromstring(response.data)
                self.assertEqual([SUGGESTED], document.xpath(
                    '//div[@id="suggestions"]//input[@name="q"]/@value'
                ))
                self.assertEqual([CORRECTED], document.xpath(
                    '//div[@id="corrections"]//input[@name="q"]/@value'
                ))
                self.assertEqual(original, document.xpath('//form[@id="search"]/descendant::input[@name="q"]/@value')[0])
                self.assertEqual('no-referrer', response.headers['Referrer-Policy'])
                self.assertIn('no-store', response.headers['Cache-Control'])

                # Source switches are settings-only, not repeated before results.
                self.assertFalse(document.xpath('//form[contains(@class,"goreecloud-refine-source")]'))
                self.assertFalse(document.xpath('//section[contains(@class,"goreecloud-source-switch")]'))

                pagination = document.xpath('//form[contains(@class, "previous_page") or '
                                            'contains(@class, "next_page") or contains(@class,"page_number")]')
                self.assertGreaterEqual(len(pagination), 12)
                for form in pagination:
                    fields = self.assert_private_form(form, terms, selected)
                    self.assertIn('pageno', fields)
                self.assert_private_form(
                    document.xpath('//form[contains(@class,"previous_page")]')[0],
                    terms, selected, '1'
                )
                next_page = document.xpath('//form[contains(@class,"next_page")]')[0]
                fields = self.assert_private_form(next_page, terms, selected, '3')
                with patch('searx.search.SearchWithPlugins', SuggestedPagedSearch):
                    followup = client.post('/search', data={**fields, 'format': 'json'}, headers=self.headers)
                    self.assertEqual(200, followup.status_code)
                    self.assertEqual(terms, followup.json['query'])
                    self.assertEqual(sorted(selected.split(',')),
                                     followup.json['goreecloud']['selected_engines'])
                    followup.close()
                response.close()

    def test_error_recovery_keeps_original_even_after_followup_generation(self):
        for original, terms, selected, page in (
            ('!sp original provider error', 'original provider error', 'startpage', '2'),
            ('original provider error', 'original provider error', 'brave,startpage', '2'),
            ('original provider error', 'original provider error', 'brave,startpage', '1'),
        ):
            with self.subTest(selected=selected, page=page), smoke.app.test_client() as client, patch(
                'searx.search.SearchWithPlugins', SuggestedFailedSearch
            ):
                request = {'q': original, 'pageno': page}
                if not original.startswith('!sp'):
                    request['engines'] = selected
                response = client.post('/search', data=request, headers=self.headers)
                self.assertEqual(200, response.status_code)
                document = html.fromstring(response.data)
                self.assertEqual([SUGGESTED], document.xpath(
                    '//div[@id="suggestions"]//input[@name="q"]/@value'
                ))
                self.assertEqual([CORRECTED], document.xpath(
                    '//div[@id="corrections"]//input[@name="q"]/@value'
                ))
                self.assertFalse(document.xpath('//form[contains(@class,"goreecloud-refine-source")]'))
                self.assertFalse(document.xpath('//section[contains(@class,"goreecloud-source-switch")]'))
                if page == '1':
                    recovery = document.xpath('//form[contains(@class,"goreecloud-empty-retry")]')
                    self.assertEqual(1, len(recovery))
                    self.assert_private_form(recovery[0], terms, selected)
                else:
                    retry = document.xpath('//form[contains(@class,"goreecloud-page-error-retry")]')
                    prev = document.xpath('//form[contains(@class,"goreecloud-previous-results")]')
                    self.assertEqual(1, len(retry))
                    self.assertEqual(1, len(prev))
                    self.assert_private_form(retry[0], terms, selected, page)
                    self.assert_private_form(prev[0], terms, selected, '1')
                response.close()

    def test_nonprivate_pagination_keeps_upstream_original_bang(self):
        with smoke.app.test_client() as client, patch.dict(
            smoke.settings['goreecloud'], {'private_search': False}
        ), patch('searx.search.SearchWithPlugins', SuggestedPagedSearch):
            response = client.post('/search', data={'q': '!sp upstream paging', 'pageno': '2'},
                                   headers=self.headers)
            self.assertEqual(200, response.status_code)
            document = html.fromstring(response.data)
            for form in document.xpath('//form[contains(@class,"previous_page") or '
                                       'contains(@class,"next_page") or contains(@class,"page_number")]'):
                fields = self.fields(form)
                self.assertEqual('!sp upstream paging', fields['q'])
                self.assertNotIn('engines', fields)
            response.close()
