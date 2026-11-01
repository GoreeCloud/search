"""Offline end-to-end result-page test: no upstream requests are made."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_runtime_smoke as smoke
from searx.search.models import SearchQuery, EngineRef


class SelectedSourcesTests(unittest.TestCase):
    def test_private_result_page_discloses_selected_sources(self):
        query = SearchQuery('synthetic sample', [
            EngineRef('brave', 'general'),
            EngineRef('brave', 'web'),
            EngineRef('startpage', 'general'),
        ], lang='en')
        result = SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )
        with smoke.app.test_client() as client:
            with patch('searx.webapp.get_search_query_from_webapp',
                       return_value=(query, None, None, None, 'en')):
                with patch('searx.search.SearchWithPlugins') as create_search:
                    create_search.return_value.search.return_value = result
                    create_search.return_value.search_query = query
                    response = client.post('/search', data={'q': 'synthetic sample'},
                                           headers={'X-Real-IP': '127.0.0.1'})
                    self.assertEqual(200, response.status_code)
                    self.assertIn(b'goreecloud-source-diagnostics', response.data)
                    self.assertIn(b'Selected:', response.data)
                    self.assertIn(b'Brave Search', response.data)
                    self.assertGreaterEqual(response.data.count(b'Brave Search'), 1)
                    self.assertIn(b'Startpage', response.data)
                    self.assertNotIn(b'goreecloud-refine-source', response.data)
                    self.assertNotIn(b'application/rss+xml', response.data)
                    self.assertNotIn(b'id="search_url"', response.data)
                    self.assertIn(b'goreecloud-wordmark', response.data)
                    self.assertIn(b'goreecloud-empty-state', response.data)
                    self.assertIn(b'No matches were returned by the selected sources.', response.data)
                    self.assertNotIn(b'goreecloud-empty-retry', response.data)
                    self.assertNotIn(b'https://searx.space', response.data)
                    create_search.assert_called_once()
                    response.close()

    def test_all_seven_provider_labels_match_selected_sources(self):
        names = ('brave', 'startpage', 'qwant', 'duckduckgo', 'ecosia', 'bing', 'google')
        display = ('Bing', 'Brave Search', 'DuckDuckGo', 'Ecosia', 'Google', 'Qwant', 'Startpage')
        query = SearchQuery('synthetic provider labels', [
            EngineRef(name, 'general') for name in names
        ], lang='en')
        result = SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )
        from lxml import html
        with smoke.app.test_client() as client, patch(
            'searx.webapp.get_search_query_from_webapp',
            return_value=(query, None, None, None, 'en'),
        ), patch('searx.search.SearchWithPlugins') as search:
            search.return_value.search.return_value = result
            search.return_value.search_query = query
            response = client.post('/search', data={'q': 'synthetic provider labels'},
                                   headers={'X-Real-IP': '127.0.0.1'})
            self.assertEqual(200, response.status_code)
            doc = html.fromstring(response.data)
            selected = doc.xpath(
                '//details[@id="goreecloud-source-diagnostics"]/p[1]'
            )
            self.assertEqual(1, len(selected))
            text = ' '.join(selected[0].text_content().split())
            self.assertEqual('Selected: ' + ' + '.join(display) + '.', text)
            self.assertNotIn('Startpage + Startpage', text)
            search.assert_called_once()
            response.close()

    def test_untrusted_source_name_is_escaped_in_html(self):
        malicious = '<img src=x onerror=alert(42)>'
        query = SearchQuery('synthetic sample', [EngineRef(malicious, 'general')], lang='en')
        result = SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )
        with smoke.app.test_client() as client, patch(
            'searx.webapp.get_search_query_from_webapp',
            return_value=(query, None, None, None, 'en'),
        ), patch('searx.search.SearchWithPlugins') as factory:
            factory.return_value.search.return_value = result
            factory.return_value.search_query = query
            response = client.post('/search', data={'q':'synthetic sample'},
                                   headers={'X-Real-IP':'127.0.0.1'})
            self.assertEqual(422, response.status_code)
            self.assertNotIn(malicious.encode('utf-8'), response.data)
            self.assertIn(b'Only approved GoreeCloud Search sources are available', response.data)
            factory.assert_not_called()
            response.close()
