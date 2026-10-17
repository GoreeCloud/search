"""True parser-to-results integration without external provider traffic."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_runtime_smoke as smoke


class SyntheticSearch:
    def __init__(self, search_query, *args):
        self.search_query = search_query

    def search(self):
        return SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )


class OfflinePostFlowTests(unittest.TestCase):
    def test_post_preserves_private_url_and_source_selection(self):
        with smoke.app.test_client() as client:
            with patch('searx.search.SearchWithPlugins', SyntheticSearch):
                response = client.post('/search', data={'q':'synthetic private browser flow'},
                                       headers={'X-Real-IP':'127.0.0.1'})
                self.assertEqual(200, response.status_code)
                self.assertIn(b'goreecloud-source-summary', response.data)
                self.assertIn(b'goreecloud-empty-state', response.data)
                self.assertNotIn(b'application/opensearchdescription+xml', response.data)
                self.assertIn('no-store', response.headers['Cache-Control'])
                response.close()

    def test_json_search_never_claims_selected_engines_responded(self):
        with smoke.app.test_client() as client:
            with patch('searx.search.SearchWithPlugins', SyntheticSearch):
                response = client.post('/search', data={'q':'synthetic private browser flow', 'format':'json'},
                                       headers={'X-Real-IP':'127.0.0.1'})
                self.assertEqual(200, response.status_code)
                self.assertTrue(response.json['goreecloud']['selection_not_contact_confirmation'])
                self.assertEqual([], response.json['results'])
                response.close()
