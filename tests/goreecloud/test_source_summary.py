"""Offline end-to-end result-page test: no upstream requests are made."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_runtime_smoke as smoke
from searx.search.models import SearchQuery, EngineRef


class SelectedSourcesTests(unittest.TestCase):
    def test_private_result_page_discloses_selected_sources(self):
        query = SearchQuery('synthetic sample', [
            EngineRef('Alpha', 'general'),
            EngineRef('alpha', 'images'),
            EngineRef('Beta', 'general'),
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
                    self.assertIn(b'2 source(s) selected', response.data)
                    self.assertIn(b'<li>Alpha</li>', response.data)
                    self.assertNotIn(b'<li>alpha</li>', response.data)
                    self.assertIn(b'<li>Beta</li>', response.data)
                    self.assertNotIn(b'application/rss+xml', response.data)
                    self.assertNotIn(b'id="search_url"', response.data)
                    self.assertIn(b'goreecloud-wordmark', response.data)
                    self.assertIn(b'goreecloud-empty-state', response.data)
                    self.assertIn(b'Review enabled search providers', response.data)
                    self.assertNotIn(b'https://searx.space', response.data)
                    create_search.assert_called_once()
                    response.close()
