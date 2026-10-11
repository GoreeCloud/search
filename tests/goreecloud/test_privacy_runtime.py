import unittest
from unittest.mock import patch
import test_runtime_smoke as smoke

class PrivateRequestTests(unittest.TestCase):
    def test_private_get_query_denied(self):
        with smoke.app.test_client() as client:
            for route in ('/', '/search'):
                response = client.get(route + '?q=confidential', headers={'X-Real-IP': '127.0.0.1'})
                self.assertEqual(405, response.status_code)
                self.assertNotIn(b'confidential', response.data)
                self.assertIn('no-store', response.headers['Cache-Control'])
                response.close()

    def test_oversized_post_does_not_dispatch(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as engine:
            response = client.post('/search', data={'q': 'x'*513}, headers={'X-Real-IP':'127.0.0.1'})
            self.assertEqual(413, response.status_code)
            engine.assert_not_called()
            response.close()

    def test_private_home_uncacheable(self):
        with smoke.app.test_client() as client:
            response = client.get('/', headers={'X-Real-IP': '127.0.0.1'})
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertIn(b'goreecloud-source-disclosure', response.data)
            response.close()

    def test_provider_fanout_blocks_execution(self):
        from searx.search.models import SearchQuery, EngineRef
        query = SearchQuery('sample', [EngineRef('source'+str(i), 'general') for i in range(33)])
        with smoke.app.test_client() as client:
            with patch('searx.webapp.get_search_query_from_webapp', return_value=(query, None, None, None, 'en')):
                with patch('searx.search.SearchWithPlugins') as executor:
                    response = client.post('/search', data={'q': 'sample'}, headers={'X-Real-IP': '127.0.0.1'})
                    self.assertEqual(422, response.status_code)
                    executor.assert_not_called()
                    response.close()
