"""Local JSON contract tests; no provider network calls."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_runtime_smoke as smoke
from searx.search.models import SearchQuery, EngineRef
from searx.webutils import get_json_response


class LocalJsonSourceMetadataTests(unittest.TestCase):
    def test_local_json_extends_upstream_contract_without_contact_claim(self):
        query = SearchQuery('synthetic query', [
            EngineRef('brave', 'general'),
            EngineRef('brave', 'web'),
            EngineRef('startpage', 'general'),
        ], lang='en')
        results = SimpleNamespace(
            redirect_url=None, get_ordered_results=lambda: [],
            answers=[], corrections=[], infoboxes=[], suggestions=[],
            unresponsive_engines=[], get_timings=lambda: [],
        )
        with smoke.app.test_client() as client:
            with patch('searx.webapp.get_search_query_from_webapp',
                       return_value=(query, None, None, None, 'en')):
                with patch('searx.search.SearchWithPlugins') as search_factory:
                    search_factory.return_value.search.return_value = results
                    response = client.post('/search', data={
                        'q': 'synthetic query', 'format': 'json',
                    }, headers={'X-Real-IP': '127.0.0.1'})
                    self.assertEqual(200, response.status_code)
                    self.assertTrue(response.is_json)
                    doc = json.loads(response.data)
                    self.assertEqual('synthetic query', doc['query'])
                    self.assertEqual([], doc['results'])
                    self.assertEqual(['brave', 'startpage'], doc['goreecloud']['selected_engines'])
                    self.assertEqual(2, doc['goreecloud']['selected_engine_count'])
                    self.assertIs(True, doc['goreecloud']['selection_not_contact_confirmation'])
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    search_factory.assert_called_once()
                    response.close()
        upstream = json.loads(get_json_response(query, results))
        self.assertNotIn('goreecloud', upstream)
