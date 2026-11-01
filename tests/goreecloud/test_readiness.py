"""Local readiness reflects initialized provider processors, not live uptime."""
import unittest
from unittest.mock import patch

import test_runtime_smoke as smoke
from searx.search.processors import PROCESSORS


class StartupReadinessTests(unittest.TestCase):
    def test_initialized_local_process_is_ready(self):
        with smoke.app.test_client() as client:
            response = client.get('/readyz', headers={'X-Real-IP':'127.0.0.1'})
            self.assertEqual(200, response.status_code)
            self.assertEqual(b'READY', response.data)
            response.close()

    def test_missing_provider_processors_fail_closed(self):
        with smoke.app.test_client() as client:
            with patch.dict(PROCESSORS, {}, clear=True):
                response = client.get('/readyz', headers={'X-Real-IP':'127.0.0.1'})
                self.assertEqual(503, response.status_code)
                self.assertEqual(b'NOT_READY', response.data)
                response.close()

    def test_readiness_reports_no_provider_details(self):
        with smoke.app.test_client() as client:
            response = client.get('/readyz', headers={'X-Real-IP':'127.0.0.1'})
            self.assertNotIn(b'engine', response.data.lower())
            self.assertEqual('text/plain', response.mimetype)
            response.close()

    def test_readiness_is_not_exposed_outside_private_profile(self):
        with smoke.app.test_client() as client:
            with patch.dict(smoke.settings['goreecloud'], {'private_search': False}):
                response = client.get('/readyz', headers={'X-Real-IP':'127.0.0.1'})
                self.assertEqual(404, response.status_code)
                response.close()
