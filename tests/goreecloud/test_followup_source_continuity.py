"""Offline provider continuity for suggestions and spelling corrections."""
import unittest
from unittest.mock import patch
from lxml import html

import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch


class FollowupSearch(OfflineSearch):
    def search(self):
        reply = super().search()
        reply.suggestions = ['suggested <offline> & "phrase"']
        reply.corrections = ['corrected "offline" phrase']
        return reply


class PrivateFollowupTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def _forms(self, document):
        return [
            ('suggestion', document.xpath('//div[@id="suggestions"]//form')[0]),
            ('correction', document.xpath('//div[@id="corrections"]//form')[0]),
        ]

    def test_approved_provider_selection_and_filters_survive_followups(self):
        for original, selection in (
            ('!sp original terms', 'startpage'),
            ('original terms', 'brave,startpage'),
            ('original terms', 'brave'),
        ):
            with self.subTest(selected=selection, original=original), smoke.app.test_client() as client:
                with patch('searx.search.SearchWithPlugins', FollowupSearch):
                    data = {
                        'q': original, 'category_general': '1',
                        'language': 'en', 'time_range': 'week',
                        'safesearch': '2', 'theme': 'simple',
                        'timeout_limit': '2.75',
                    }
                    if not original.startswith('!sp'):
                        data['engines'] = selection
                    response = client.post('/search', data=data, headers=self.headers)
                    self.assertEqual(200, response.status_code)
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    self.assertEqual('no-referrer', response.headers['Referrer-Policy'])
                    self.assertNotIn('Set-Cookie', response.headers)
                    document = html.fromstring(response.data)
                    # Engine choice moved to Preferences. Suggestions and corrections
                    # must still preserve the effective engine/category selection.
                    self.assertFalse(document.xpath('//form[contains(@class, "goreecloud-refine-source")]'))
                    first_followup = self._forms(document)[0][1]
                    effective_categories = {
                        field.get('name'): field.get('value')
                        for field in first_followup.xpath('.//input[starts-with(@name, "category_")]')
                    }
                    if not original.startswith('!sp'):
                        self.assertEqual('1', effective_categories.get('category_general'))
                    for kind, form in self._forms(document):
                        with self.subTest(kind=kind):
                            values = {node.get('name'): node.get('value') for node in form.xpath('.//input[@type="hidden"]')}
                            self.assertEqual('post', form.get('method').lower())
                            self.assertEqual('/search', form.get('action'))
                            self.assertEqual('suggested <offline> & "phrase"' if kind == 'suggestion' else 'corrected "offline" phrase', values['q'])
                            self.assertEqual(selection, values['engines'])
                            self.assertNotIn('!sp', values['q'])
                            followup_categories = {
                                key: value for key, value in values.items()
                                if key.startswith('category_')
                            }
                            self.assertEqual(effective_categories, followup_categories)
                            for key in ('language', 'safesearch', 'time_range', 'theme', 'timeout_limit'):
                                self.assertEqual(data[key], values[key])
                            self.assertNotIn('q=', form.get('action'))
                            repeat = client.post('/search', data={**values, 'format':'json'}, headers=self.headers)
                            self.assertEqual(200, repeat.status_code)
                            self.assertEqual(sorted(selection.split(',')), repeat.json['goreecloud']['selected_engines'])
                            self.assertEqual(values['q'], repeat.json['query'])
                            self.assertNotIn('Location', repeat.headers)
                            repeat.close()
                    response.close()

    def test_nonprivate_followups_retain_upstream_bang_without_post_engine_field(self):
        with smoke.app.test_client() as client, patch.dict(
            smoke.settings['goreecloud'], {'private_search': False}
        ), patch('searx.search.SearchWithPlugins', FollowupSearch):
            response = client.post('/search', data={'q': '!sp original terms'}, headers=self.headers)
            self.assertEqual(200, response.status_code)
            document = html.fromstring(response.data)
            for _, form in self._forms(document):
                inputs = {node.get('name'): node.get('value') for node in form.xpath('.//input[@type="hidden"]')}
                self.assertNotIn('engines', inputs)
                self.assertTrue(inputs['q'].startswith('!sp '))
            response.close()
