"""Private Search must not auto-apply shared or attacker-supplied preferences."""
import unittest
from unittest.mock import patch

import test_runtime_smoke as smoke


class PrivatePreferenceImportTests(unittest.TestCase):
    def test_shared_preferences_get_never_imports_or_sets_cookie(self):
        with smoke.app.test_client() as client, patch(
            'searx.webapp.Preferences.parse_encoded_data'
        ) as importer:
            for route in ('/', '/preferences', '/search'):
                with self.subTest(route=route):
                    response = client.get(
                        route + '?preferences=synthetic_secret_marker',
                        headers={'X-Real-IP': '127.0.0.1'},
                    )
                    self.assertEqual(422, response.status_code)
                    self.assertNotIn(b'synthetic_secret_marker', response.data)
                    self.assertNotIn('Set-Cookie', response.headers)
                    self.assertNotIn('Location', response.headers)
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    self.assertIn(b'Return to GoreeCloud Search', response.data)
                    response.close()
            importer.assert_not_called()

    def test_serialized_preferences_post_is_not_processed(self):
        with smoke.app.test_client() as client, patch(
            'searx.webapp.Preferences.parse_encoded_data'
        ) as importer, patch('searx.search.SearchWithPlugins') as provider:
            response = client.post('/search', data={
                'q': 'synthetic query', 'preferences': 'synthetic_secret_marker',
            }, headers={'X-Real-IP': '127.0.0.1'})
            self.assertEqual(422, response.status_code)
            self.assertNotIn('Set-Cookie', response.headers)
            importer.assert_not_called()
            provider.assert_not_called()
            response.close()

    def test_local_preference_form_remains_available(self):
        with smoke.app.test_client() as client:
            response = client.get('/preferences', headers={'X-Real-IP': '127.0.0.1'})
            self.assertEqual(200, response.status_code)
            self.assertIn(b'Changes here are saved to this browser', response.data)
            self.assertIn(b'shared URL is disabled', response.data)
            self.assertIn('no-store', response.headers['Cache-Control'])
            response.close()
