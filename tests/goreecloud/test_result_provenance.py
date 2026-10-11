"""Offline test: selected sources vs source labels on visible safe results."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_runtime_smoke as smoke
from searx.goreecloud_policy import represented_result_sources
from searx.result_types import LegacyResult
from searx.search.models import EngineRef, SearchQuery


def fixture():
    first = LegacyResult(url='https://example.org/one', title='First document', content='One',
                         engine='brave', engines={'brave', 'STARTPAGE', 'Unexpected'})
    second = LegacyResult(url='https://example.org/two', title='Second document', content='Two',
                          engine='startpage', engines={'startpage'})
    denied = LegacyResult(url='javascript:alert(1)', title='Unsafe document', content='No',
                          engine='Missing', engines={'Missing'})
    for result in (first, second, denied):
        result.normalize_result_fields()
    container = SimpleNamespace(
        redirect_url=None, suggestions=[], corrections=[], answers=[],
        infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
        get_timings=lambda: [], get_ordered_results=lambda: [first, second, denied],
    )
    query = SearchQuery('synthetic', [EngineRef('brave', 'general'), EngineRef('startpage', 'general')], lang='en')
    return query, container


class ResultProvenanceTests(unittest.TestCase):
    def test_overlapping_attribution_is_not_provider_contact(self):
        query, container = fixture()
        visible = container.get_ordered_results()[:2]
        selected = (ref.name for ref in query.engineref_list)
        self.assertEqual({'brave': 1, 'startpage': 2}, represented_result_sources(visible, selected))
        self.assertEqual({}, represented_result_sources([], ['brave', 'startpage']))
        self.assertEqual({}, represented_result_sources(visible, ['Unknown']))

    def test_html_and_json_report_only_labels_of_safe_visible_results(self):
        for fmt in ('html', 'json'):
            with self.subTest(format=fmt):
                query, results = fixture()
                with smoke.app.test_client() as client, patch(
                    'searx.webapp.get_search_query_from_webapp',
                    return_value=(query, None, None, None, 'en'),
                ), patch('searx.search.SearchWithPlugins') as runner:
                    runner.return_value.search.return_value = results
                    runner.return_value.search_query = query
                    response = client.post('/search', data={'q':'synthetic', 'format':fmt},
                                           headers={'X-Real-IP':'127.0.0.1'})
                    self.assertEqual(200, response.status_code)
                    if fmt == 'json':
                        metadata = response.json['goreecloud']
                        self.assertEqual(2, metadata['selected_engine_count'])
                        self.assertEqual(['brave', 'startpage'], metadata['represented_engines'])
                        self.assertEqual({'brave': 1, 'startpage': 2}, metadata['represented_result_counts'])
                        self.assertIs(True, metadata['representation_not_contact_confirmation'])
                        self.assertEqual(2, len(response.json['results']))
                    else:
                        self.assertIn(b'2 source(s) selected', response.data)
                        self.assertIn(b'2 selected source(s) represented', response.data)
                        self.assertIn('Brave Search — 1 displayed result(s)'.encode(), response.data)
                        self.assertIn('Startpage — 2 displayed result(s)'.encode(), response.data)
                        self.assertNotIn('Missing — 1 displayed'.encode(), response.data)
                        self.assertNotIn(b'Unsafe document', response.data)
                    runner.assert_called_once()
                    response.close()
