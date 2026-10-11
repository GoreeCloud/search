"""Source-only refinement using POST with no URL query, no real engine I/O."""
import unittest
from unittest.mock import patch

from lxml import html
import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch


class SourceRefinementTests(unittest.TestCase):
    def test_result_source_only_action_preserves_query_privacy_and_limits_engine(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            page = client.post('/search', data={'q':'synthetic source refinement'},
                               headers={'X-Real-IP':'127.0.0.1'})
            self.assertEqual(200, page.status_code)
            root = html.fromstring(page.data)
            forms = root.xpath('//form[contains(@class,"goreecloud-refine-source")]')
            self.assertGreater(len(forms), 1)
            selected = forms[0]
            self.assertEqual('post', selected.get('method'))
            self.assertEqual('/search', selected.get('action'))
            fields = {node.get('name'): node.get('value') for node in selected.xpath('.//input')}
            self.assertEqual('synthetic source refinement', fields['q'])
            self.assertTrue(fields['engines'])
            self.assertFalse(any(key.startswith('category_') for key in fields))
            self.assertNotIn('preferences', fields)
            self.assertNotIn('Location', page.headers)
            page.close()

            response = client.post('/search', data={**fields, 'format':'json'},
                                   headers={'X-Real-IP':'127.0.0.1'})
            self.assertEqual(200, response.status_code)
            self.assertEqual([fields['engines']], response.json['goreecloud']['selected_engines'])
            self.assertIn('no-store', response.headers['Cache-Control'])
            response.close()

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
            self.assertEqual(200, response.status_code)
            root = html.fromstring(response.data)
            fields = root.xpath('//form[contains(@class,"goreecloud-refine-source")]//input[@name="engines"]')
            self.assertEqual(1, len(fields))
            self.assertEqual(risky, fields[0].get('value'))
            self.assertNotIn('onclick="alert(99)"', response.get_data(as_text=True))
            response.close()
