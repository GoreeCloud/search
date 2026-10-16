"""No-provider privacy preflight and explicit continuation regression tests."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lxml import html
import test_runtime_smoke as smoke


class OfflineSearch:
    def __init__(self, search_query, *args):
        self.search_query = search_query

    def search(self):
        return SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )


class SearchPreviewTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_private_home_exposes_a_post_only_preview_action(self):
        with smoke.app.test_client() as client:
            response = client.get('/', headers=self.headers)
            page = html.fromstring(response.data)
            buttons = page.xpath('//form[@id="search"]//div[@id="search_view"]//button[@formaction="/preview"][not(ancestor::noscript)]')
            self.assertEqual(1, len(buttons))
            self.assertEqual('button', buttons[0].get('type'))
            self.assertEqual('post', buttons[0].get('formmethod'))
            self.assertIsNotNone(buttons[0].get('formnovalidate'))
            self.assertEqual(1, len(page.xpath('//script[contains(@src,"goreecloud-preview.js")]')))
            response.close()
            asset = client.get('/static/themes/simple/goreecloud-preview.js', headers=self.headers)
            self.assertEqual(200, asset.status_code)
            self.assertIn(b'goreecloud-preview-trigger', asset.data)
            self.assertIn(b'destination.origin !== location.origin', asset.data)
            self.assertIn(b'new FormData(searchForm)', asset.data)
            self.assertIn(b'HTMLFormElement.prototype.submit.call(submission)', asset.data)
            asset.close()

    def test_preview_preserves_search_selection_without_network_execution(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as network:
            response = client.post('/preview', data={
                'q': 'synthetic preview query', 'category_general': '1',
                'language':'en', 'safesearch':'2',
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertEqual('no-referrer', response.headers['Referrer-Policy'])
            page = html.fromstring(response.data)
            self.assertIn('No search-provider requests have been sent.', page.text_content())
            self.assertGreater(len(page.xpath('//section[contains(@class,"goreecloud-preview")]//li')), 0)
            all_form = page.xpath('//form[@action="/search"]')[0]
            sent = {node.get('name'):node.get('value') for node in all_form.xpath('.//input')}
            self.assertEqual('synthetic preview query', sent['q'])
            self.assertEqual('2', sent['safesearch'])
            self.assertEqual('en', sent['language'])
            self.assertEqual('1', sent['category_general'])
            self.assertNotIn('format', sent)
            self.assertNotIn('preferences', sent)
            self.assertNotIn('Location', response.headers)
            network.assert_not_called()
            response.close()

            with patch('searx.search.SearchWithPlugins', OfflineSearch):
                search = client.post('/search', data=sent, headers=self.headers)
                self.assertEqual(200, search.status_code)
                self.assertIn(b'goreecloud-source-summary', search.data)
                search.close()

    def test_single_source_selection_can_be_submitted_without_other_categories(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as network:
            response = client.post('/preview', data={'q':'synthetic provider selection'}, headers=self.headers)
            self.assertEqual(200, response.status_code)
            page = html.fromstring(response.data)
            forms = page.xpath('//form[@action="/search"]')
            self.assertEqual(2, len(forms))
            single = forms[1]
            self.assertFalse(single.xpath('.//input[starts-with(@name,"category_")]'))
            sources = single.xpath('.//select[@name="engines"]/option[@value!=""]/@value')
            self.assertGreater(len(sources), 1)
            fields = {node.get('name'):node.get('value') for node in single.xpath('.//input')}
            fields['engines'] = sources[0]
            network.assert_not_called()
            response.close()
            with patch('searx.search.SearchWithPlugins', OfflineSearch):
                searched = client.post('/search', data={**fields, 'format':'json'}, headers=self.headers)
                self.assertEqual(200, searched.status_code)
                self.assertEqual([sources[0]], searched.json['goreecloud']['selected_engines'])
                searched.close()

    def test_private_json_preflight_returns_selection_without_query_or_egress(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as network:
            marker = 'not-sent-private-marker'
            response = client.post('/preview', data={'q':marker, 'format':'json'}, headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertTrue(response.is_json)
            info = response.json['goreecloud']
            self.assertEqual('private_search_preview', info['mode'])
            self.assertIs(False, info['network_requests_made'])
            self.assertEqual(len(marker), info['query_length'])
            self.assertEqual(len(info['selected_engines']), info['selected_engine_count'])
            self.assertTrue(info['selection_not_contact_confirmation'])
            self.assertNotIn(marker, response.get_data(as_text=True))
            self.assertIn('no-store', response.headers['Cache-Control'])
            network.assert_not_called()
            response.close()

    def test_empty_query_previews_selected_sources_without_provider_egress(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as network:
            for payload in ({}, {'q': ''}, {'q': '   '}, {'q': '', 'engines': 'brave'}):
                with self.subTest(payload=payload):
                    response = client.post('/preview', data=payload, headers=self.headers)
                    self.assertEqual(200, response.status_code)
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    self.assertEqual('no-referrer', response.headers['Referrer-Policy'])
                    self.assertNotIn('Location', response.headers)
                    page = html.fromstring(response.data)
                    self.assertIn('No search-provider requests have been sent.', page.text_content())
                    self.assertIn('No search terms have been entered', page.text_content())
                    items = page.xpath('//section[contains(@class,"goreecloud-preview")]//li')
                    self.assertGreaterEqual(len(items), 1)
                    text_inputs = page.xpath('//form[@action="/search"]//input[@name="q"][@type="search"][@required]')
                    self.assertEqual(2 if len(items) > 1 else 1, len(text_inputs))
                    self.assertFalse(page.xpath('//form[@action="/search"]//input[@name="q"][@type="hidden"]'))
                    self.assertNotIn(b'goreecloud source selection preview', response.data)
                    network.assert_not_called()
                    response.close()

    def test_empty_query_json_preflight_does_not_emit_or_send_internal_marker(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as network:
            response = client.post('/preview', data={'q': '', 'format': 'json'}, headers=self.headers)
            self.assertEqual(200, response.status_code)
            info = response.json['goreecloud']
            self.assertEqual(0, info['query_length'])
            self.assertIs(False, info['query_provided'])
            self.assertIs(False, info['will_contact_providers_on_continue'])
            self.assertIs(False, info['network_requests_made'])
            self.assertGreaterEqual(info['selected_engine_count'], 1)
            self.assertNotIn('goreecloud source selection preview', response.get_data(as_text=True))
            self.assertIn('no-store', response.headers['Cache-Control'])
            network.assert_not_called()
            response.close()

    def test_invalid_preview_requests_fail_before_execution(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as network:
            for method, url, data, status in (
                ('GET', '/preview?q=private-marker', None, 405),
                ('POST', '/preview?q=private-marker', {'q':'ok'}, 405),
                ('POST', '/preview', {'q':'x'*513}, 413),
                ('POST', '/preview', {'q':'!!ddg sample', 'format':'json'}, 422),
                ('POST', '/preview', {'q':'!! sample'}, 422),
            ):
                with self.subTest(method=method, url=url, status=status):
                    response = client.open(url, method=method, data=data, headers=self.headers)
                    self.assertEqual(status, response.status_code)
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    self.assertNotIn('Location', response.headers)
                    self.assertNotIn(b'private-marker', response.data)
                    response.close()
            network.assert_not_called()

    def test_startpage_warning_only_appears_when_that_provider_is_selected(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as network:
            for selected, show_warning in (('brave', False), ('startpage', True), ('brave,startpage', True)):
                with self.subTest(selected=selected):
                    response = client.post('/preview', data={'q': 'synthetic provider selection', 'engines': selected}, headers=self.headers)
                    self.assertEqual(200, response.status_code)
                    page = html.fromstring(response.data)
                    warnings = page.xpath('//*[@role="note" and contains(@class, "goreecloud-startpage-note")]')
                    self.assertEqual(1 if show_warning else 0, len(warnings))
                    if show_warning:
                        self.assertIn('not checked', warnings[0].text_content())
                        self.assertIn('No other provider will be substituted.', warnings[0].text_content())
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    response.close()
            network.assert_not_called()

    def test_preflight_is_hidden_without_private_search_mode(self):
        with smoke.app.test_client() as client, patch.dict(smoke.settings['goreecloud'], {'private_search':False}):
            response = client.post('/preview', data={'q':'synthetic'}, headers=self.headers)
            self.assertEqual(404, response.status_code)
            response.close()
