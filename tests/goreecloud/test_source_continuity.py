"""No-network checks: provider choices survive pagination and explicit switches."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from lxml import html

import test_runtime_smoke as smoke
from searx.result_types import LegacyResult


class PagedSearch:
    def __init__(self, search_query, *args):
        self.search_query = search_query

    def search(self):
        result = LegacyResult(url='https://example.org/synthetic', title='Synthetic page', content='Fixture')
        result.normalize_result_fields()
        return SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=True, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [result],
        )


class ProviderContinuityTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_single_source_survives_header_and_all_pagination_forms(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', PagedSearch):
            for provider in ('brave', 'startpage'):
                with self.subTest(provider=provider):
                    reply = client.post('/search', data={'q':'synthetic paging', 'engines':provider,
                                                         'pageno':'2'}, headers=self.headers)
                    self.assertEqual(200,reply.status_code)
                    doc = html.fromstring(reply.data)
                    forms = doc.xpath('//form[@id="search" or contains(@class,"previous_page") or contains(@class,"next_page") or contains(@class,"page_number")]')
                    self.assertGreaterEqual(len(forms), 12)
                    for form in forms:
                        values = form.xpath('.//input[@name="engines"]/@value')
                        self.assertEqual([provider], values,form.get('class'))
                        self.assertEqual('post',form.get('method').lower())
                        self.assertEqual('/search',form.get('action'))
                    next_form = doc.xpath('//form[contains(@class,"next_page")]')[0]
                    body = {e.get('name'):e.get('value') for e in next_form.xpath('.//input')}
                    continued = client.post('/search',data={**body,'format':'json'}, headers=self.headers)
                    self.assertEqual(200,continued.status_code)
                    self.assertEqual([provider],continued.json['goreecloud']['selected_engines'])
                    continued.close()
                    reply.close()

    def test_switch_toolbar_has_only_both_brave_and_startpage_post_actions(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', PagedSearch):
            reply = client.post('/search',data={'q':'!sp synthetic terms'},headers=self.headers)
            self.assertEqual(200,reply.status_code)
            doc=html.fromstring(reply.data)
            toolbar=doc.xpath('//section[contains(@class,"goreecloud-source-switch")]')
            self.assertEqual(1,len(toolbar))
            forms=toolbar[0].xpath('.//form')
            self.assertEqual(3,len(forms))
            expected=['brave,startpage','brave','startpage']
            for form,provider in zip(forms,expected):
                self.assertEqual('/search',form.get('action'))
                self.assertEqual('post',form.get('method').lower())
                self.assertEqual([provider],form.xpath('.//input[@name="engines"]/@value'))
                self.assertEqual(['synthetic terms'],form.xpath('.//input[@name="q"]/@value'))
                self.assertEqual(provider=='startpage',bool(form.xpath('.//button[@disabled]')))
                fields={element.get('name'):element.get('value') for element in form.xpath('.//input')}
                next_reply=client.post('/search',data={**fields,'format':'json'},headers=self.headers)
                self.assertEqual(200,next_reply.status_code)
                self.assertEqual(sorted(provider.split(',')),next_reply.json['goreecloud']['selected_engines'])
                next_reply.close()
            reply.close()

    def test_switch_does_not_modify_saved_browser_preferences(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', PagedSearch):
            before=client.get('/preferences',headers=self.headers)
            self.assertEqual(200,before.status_code)
            before.close()
            for provider in ('brave','startpage','brave,startpage'):
                reply=client.post('/search',data={'q':'synthetic search','engines':provider},headers=self.headers)
                self.assertEqual(200,reply.status_code)
                self.assertNotIn('Set-Cookie',reply.headers)
                self.assertIn('no-store',reply.headers['Cache-Control'])
                reply.close()
