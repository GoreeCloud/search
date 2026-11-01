"""Source-only refinement using POST with no URL query, no real engine I/O."""
import unittest
from unittest.mock import patch

from lxml import html
import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch


class SourceRefinementTests(unittest.TestCase):
    def test_explicit_post_selection_preserves_query_privacy_and_filters(self):
        headers = {'X-Real-IP': '127.0.0.1'}
        values = {
            'q': 'synthetic source refinement', 'engines': 'startpage',
            'category_general': '1', 'language': 'en', 'safesearch': '2',
            'time_range': 'week', 'theme': 'simple', 'timeout_limit': '2.75',
        }
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            page = client.post('/search', data=values, headers=headers)
            self.assertEqual(200, page.status_code)
            doc = html.fromstring(page.data)
            self.assertFalse(doc.xpath('//form[contains(@class,"goreecloud-refine-source")]'))
            self.assertFalse(doc.xpath('//section[contains(@class,"goreecloud-source-switch")]'))
            self.assertNotIn('Location', page.headers)
            self.assertIn('no-store', page.headers['Cache-Control'])
            page.close()
            selected = client.post('/search', data={**values, 'format': 'json'}, headers=headers)
            self.assertEqual(200, selected.status_code)
            self.assertEqual(['startpage'], selected.json['goreecloud']['selected_engines'])
            self.assertEqual(values['q'], selected.json['query'])
            self.assertNotIn('Location', selected.headers)
            selected.close()

    def test_source_only_action_does_not_echo_untrusted_provider_html(self):
        # Rendering uses autoescaping, including hidden inputs and button labels.
        from types import SimpleNamespace
        from searx.search.models import EngineRef, SearchQuery
        risky = 'Demo\" onclick=\"alert(99)'
        query = SearchQuery('synthetic query', [EngineRef(risky, 'general')], lang='en')
        results = SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )
        with smoke.app.test_client() as client, patch(
            'searx.webapp.get_search_query_from_webapp',
            return_value=(query, None, None, None, 'en'),
        ), patch('searx.search.SearchWithPlugins') as fake:
            fake.return_value.search.return_value = results
            fake.return_value.search_query = query
            response = client.post('/search', data={'q':'synthetic query'},
                                   headers={'X-Real-IP':'127.0.0.1'})
            self.assertEqual(422, response.status_code)
            self.assertNotIn(risky, response.get_data(as_text=True))
            self.assertIn(b'Only approved GoreeCloud Search sources are available', response.data)
            fake.assert_not_called()
            response.close()
