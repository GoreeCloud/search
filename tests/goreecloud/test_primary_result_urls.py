"""No-provider test of safe primary result destinations in private Search."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_runtime_smoke as smoke
from searx.goreecloud_policy import safe_primary_result_url
from searx.result_types import LegacyResult
from searx.search.models import EngineRef, SearchQuery
from searx.webutils import get_json_response


def synthetic_results():
    safe = LegacyResult(url='https://example.org/safe-result', title='Trusted synthetic', content='Sample')
    unsafe = LegacyResult(url='javascript:alert(42)', title='Unsafe synthetic', content='Sample')
    for result in (safe, unsafe):
        result.normalize_result_fields()
    return SimpleNamespace(
        redirect_url=None, suggestions=[], corrections=[], answers=[],
        infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
        get_timings=lambda: [], get_ordered_results=lambda: [safe, unsafe],
    )


class PrivatePrimaryResultUrlTests(unittest.TestCase):
    def test_url_scheme_and_authority_guards(self):
        for url in ('https://example.org/path', 'http://example.org', 'HTTPS://example.org/',
                    'https://example.org:443/path', 'http://[2001:db8::1]:8443/result'):
            with self.subTest(valid=url):
                self.assertTrue(safe_primary_result_url(url))
        for url in ('javascript:alert(42)', 'data:text/html,hello', 'file:///etc/passwd',
                    'ftp://example.org/', '//example.org/', 'https:///no-host',
                    'https://user:pass@example.org/', 'https://example.org\\@bad.test/',
                    'https://example.org\nmalformed', 'https://example.org%40spoof.test/',
                    'https://example.org:invalid/path', 'https://example.org:65536/',
                    'https://example.org:0/', 'https://example.org/path\u202e',
                    'https://example.org/\u2066unclosed', 'https://example.org/\u200bhidden',
                    '', None):
            with self.subTest(denied=url):
                self.assertFalse(safe_primary_result_url(url))

    def test_html_omits_unsafe_primary_links(self):
        query = SearchQuery('synthetic', [EngineRef('brave', 'general')], lang='en')
        with smoke.app.test_client() as client, patch(
            'searx.webapp.get_search_query_from_webapp', return_value=(query, None, None, None, 'en')
        ), patch('searx.search.SearchWithPlugins') as engine:
            engine.return_value.search.return_value = synthetic_results()
            engine.return_value.search_query = query
            response = client.post('/search', data={'q':'synthetic'}, headers={'X-Real-IP':'127.0.0.1'})
            self.assertEqual(200, response.status_code)
            self.assertIn(b'Trusted <span class="highlight">synthetic</span>', response.data)
            self.assertNotIn(b'Unsafe synthetic', response.data)
            self.assertNotIn(b'javascript:alert(42)', response.data)
            response.close()

    def test_private_json_omits_unsafe_result_while_upstream_is_untouched(self):
        query = SearchQuery('synthetic', [EngineRef('brave', 'general')], lang='en')
        data = synthetic_results()
        private_doc = json.loads(get_json_response(query, data, include_source_selection=True))
        upstream_doc = json.loads(get_json_response(query, data))
        self.assertEqual(['https://example.org/safe-result'], [r['url'] for r in private_doc['results']])
        self.assertEqual(2, len(upstream_doc['results']))
