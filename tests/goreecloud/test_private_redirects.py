"""Synthetic provider isolation: no public network/search requests."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_runtime_smoke as smoke
from searx.search.models import EngineRef, SearchQuery
from searx.goreecloud_policy import SearchPolicyViolation, validate_no_external_redirects


class PrivateRedirectTests(unittest.TestCase):
    def test_direct_navigation_operators_denied_before_provider_dispatch(self):
        for field, value in (('external_bang', 'g'), ('redirect_to_first_result', True)):
            with self.subTest(field=field):
                query = SearchQuery('sample', [EngineRef('demo', 'general')], **{field: value})
                with smoke.app.test_client() as client:
                    with patch('searx.webapp.get_search_query_from_webapp', return_value=(query, None, None, None, 'en')):
                        with patch('searx.search.SearchWithPlugins') as execute:
                            response = client.post('/search', data={'q': 'sample'},
                                                   headers={'X-Real-IP':'127.0.0.1'})
                            self.assertEqual(422, response.status_code)
                            self.assertNotIn('Location', response.headers)
                            execute.assert_not_called()
                            response.close()

    def test_upstream_redirect_is_blocked_after_mock_search(self):
        query = SearchQuery('sample', [EngineRef('demo', 'general')])
        result = SimpleNamespace(redirect_url='https://outside.invalid/?q=sample', get_timings=lambda: [])
        with smoke.app.test_client() as client:
            with patch('searx.webapp.get_search_query_from_webapp', return_value=(query, None, None, None, 'en')):
                with patch('searx.search.SearchWithPlugins') as execute:
                    execute.return_value.search.return_value = result
                    response = client.post('/search', data={'q':'sample'}, headers={'X-Real-IP':'127.0.0.1'})
                    self.assertEqual(422, response.status_code)
                    self.assertNotIn('Location', response.headers)
                    self.assertNotIn(b'outside.invalid', response.data)
                    response.close()

    def test_rewrite_cannot_bypass_raw_query_limit(self):
        query = SearchQuery('short', [EngineRef('demo', 'general')])
        with smoke.app.test_client() as client:
            with patch('searx.webapp.get_search_query_from_webapp', return_value=(query, None, None, None, 'en')) as parser:
                with patch('searx.search.SearchWithPlugins') as execute:
                    response = client.post('/search', data={'q':'!' * 514}, headers={'X-Real-IP':'127.0.0.1'})
                    self.assertEqual(413, response.status_code)
                    parser.assert_not_called()
                    execute.assert_not_called()
                    response.close()

    def test_empty_url_query_rejected(self):
        with smoke.app.test_client() as client:
            response = client.get('/search?q=', headers={'X-Real-IP':'127.0.0.1'})
            self.assertEqual(405, response.status_code)
            response.close()

    def test_normal_search_controls_are_allowed(self):
        validate_no_external_redirects(external_bang=None, lucky_redirect=False)
        for args in ({'external_bang':'wiki','lucky_redirect':False}, {'external_bang':None,'lucky_redirect':True}):
            with self.assertRaises(SearchPolicyViolation):
                validate_no_external_redirects(**args)

    def test_real_query_parser_denies_redirect_operators(self):
        with smoke.app.test_client() as client:
            for query in ('!!ddg sample', '!! sample'):
                with self.subTest(query=query):
                    with patch('searx.search.SearchWithPlugins') as execute:
                        response = client.post('/search', data={'q': query},
                                               headers={'X-Real-IP': '127.0.0.1'})
                        self.assertEqual(422, response.status_code)
                        execute.assert_not_called()
                        response.close()
