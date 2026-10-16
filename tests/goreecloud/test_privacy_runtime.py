import unittest
from unittest.mock import patch
import test_runtime_smoke as smoke

class PrivateRequestTests(unittest.TestCase):
    def test_local_host_rejects_dns_rebinding_before_dispatch(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as engine:
            for host in ('search.attacker.test', 'localhost.attacker.test', '127.0.0.2', 'localhost:0'):
                with self.subTest(host=host):
                    response = client.post('/search', data={'q': 'synthetic'}, headers={'Host': host})
                    self.assertEqual(403, response.status_code)
                    self.assertNotIn(b'synthetic', response.data)
                    response.close()
            engine.assert_not_called()

    def test_private_post_rejects_cross_origin_and_cross_site_browser_forms(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as engine:
            cases = (
                {'Origin': 'https://other.example'},
                {'Origin': 'http://localhost.attacker.test'},
                {'Origin': 'null'},
                {'Sec-Fetch-Site': 'cross-site'},
                {'Sec-Fetch-Site': 'same-site'},
            )
            for headers in cases:
                with self.subTest(headers=headers):
                    response = client.post('/search', data={'q': 'synthetic'}, headers=headers)
                    self.assertEqual(403, response.status_code)
                    self.assertNotIn(b'synthetic', response.data)
                    response.close()
            engine.assert_not_called()

    def test_same_origin_private_preview_still_works(self):
        with smoke.app.test_client() as client:
            response = client.post('/preview', data={'q': 'synthetic', 'format': 'json'}, headers={
                'Origin': 'http://localhost', 'Sec-Fetch-Site': 'same-origin',
            })
            self.assertEqual(200, response.status_code)
            self.assertFalse(response.json['goreecloud']['network_requests_made'])
            response.close()

    def test_oversized_private_form_is_rejected_before_dispatch(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as engine:
            response = client.post('/search', data={
                'q': 'synthetic', 'padding': 'x' * 65536,
            })
            self.assertEqual(413, response.status_code)
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertNotIn(b'synthetic', response.data)
            engine.assert_not_called()
            response.close()

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
            self.assertNotIn(b'application/opensearchdescription+xml', response.data)
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
