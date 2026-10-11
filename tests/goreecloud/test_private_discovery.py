"""Private mode disables unadvertised GET-based browser discovery too."""
import unittest
from unittest.mock import patch

import test_runtime_smoke as smoke


class PrivateDiscoveryTests(unittest.TestCase):
    def test_browser_discovery_and_autocomplete_are_not_exposed(self):
        with smoke.app.test_client() as client:
            for path in ('/opensearch.xml', '/autocompleter?q=private-marker-secret'):
                for headers in ({'User-Agent':'Mozilla/5.0 Chrome Safari WebKit'},
                                {'X-Requested-With':'XMLHttpRequest'}):
                    with self.subTest(path=path, headers=headers):
                        response = client.get(path, headers={**headers, 'X-Real-IP':'127.0.0.1'})
                        self.assertEqual(404, response.status_code)
                        self.assertNotIn('private-marker-secret', response.get_data(as_text=True))
                        self.assertIn('no-store', response.headers['Cache-Control'])
                        self.assertEqual('no-referrer', response.headers['Referrer-Policy'])
                        response.close()

    def test_discovery_remains_upstream_compatible_without_private_profile(self):
        with smoke.app.test_client() as client:
            with patch.dict(smoke.settings['goreecloud'], {'private_search':False}):
                response = client.get('/opensearch.xml', headers={'X-Real-IP':'127.0.0.1'})
                self.assertEqual(200, response.status_code)
                self.assertIn('application/opensearchdescription+xml', response.content_type)
                response.close()
