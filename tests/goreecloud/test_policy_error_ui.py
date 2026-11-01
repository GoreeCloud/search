"""Policy refusals must be accessible and never echo search terms."""
import unittest
import test_runtime_smoke as smoke


class PolicyErrorUiTests(unittest.TestCase):
    def test_html_policy_page_has_accessible_recovery(self):
        with smoke.app.test_client() as client:
            for method, path, data, status in (
                ('GET', '/search?q=private-marker-secret', None, 405),
                ('POST', '/search', {'q': 'private-marker-secret' + 'x'*512}, 413),
                ('POST', '/search', {'q': '!!ddg private-marker-secret'}, 422),
            ):
                with self.subTest(status=status):
                    response = client.open(path, method=method, data=data,
                                           headers={'X-Real-IP':'127.0.0.1'})
                    self.assertEqual(status, response.status_code)
                    self.assertIn(b'role="alert"', response.data)
                    self.assertIn(b'Return to GoreeCloud Search', response.data)
                    self.assertNotIn(b'private-marker-secret', response.data)
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    response.close()

    def test_json_refusal_is_structured_no_query_reflection(self):
        with smoke.app.test_client() as client:
            response = client.post('/search', data={'q': '!!ddg private-marker-secret', 'format':'json'},
                                   headers={'X-Real-IP':'127.0.0.1'})
            self.assertEqual(422, response.status_code)
            self.assertEqual('private_search_policy_violation', response.json['goreecloud']['code'])
            self.assertNotIn(b'private-marker-secret', response.data)
            self.assertIn('no-store', response.headers['Cache-Control'])
            response.close()
