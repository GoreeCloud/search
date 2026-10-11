import unittest
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-runtime-smoke-test-only-secret-0000')
from searx.goreecloud_policy import validate_transport, validate_disclosure, SearchPolicyViolation

class PolicyTests(unittest.TestCase):
    def test_post_only(self):
        validate_transport(method='POST', query_in_url=False, private=True)
        with self.assertRaises(SearchPolicyViolation):
            validate_transport(method='GET', query_in_url=True, private=True)

    def test_provider_budget(self):
        self.assertEqual(2, validate_disclosure('q', ['A', 'a', 'B'], max_query_chars=512, max_providers=2))
        with self.assertRaises(SearchPolicyViolation):
            validate_disclosure('q', ['a', 'b', 'c'], max_query_chars=512, max_providers=2)
