"""Offline admission tests for VPN-only, single-worker free metasearch."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import test_runtime_smoke as smoke
from searx.goreecloud_request_budget import RequestBudget


class FreeBudgetContractTests(unittest.TestCase):
    def test_burst_throttle_and_exact_window_expiration(self):
        b = RequestBudget(3)
        self.assertEqual((True, 0), b.admit(now=100))
        self.assertEqual((True, 0), b.admit(now=101))
        self.assertEqual((True, 0), b.admit(now=102))
        self.assertEqual((False, 30), b.admit(now=130))
        self.assertEqual((False, 1), b.admit(now=159.9))
        self.assertEqual((True, 0), b.admit(now=160))
        self.assertEqual((False, 1), b.admit(now=160))

    def test_global_not_ip_or_query_profiling(self):
        b = RequestBudget(1)
        self.assertEqual((True, 0), b.admit(now=10))
        self.assertEqual((False, 60), b.admit(now=10))
        self.assertEqual(1, len(b._recent))
        self.assertEqual([10], list(b._recent))

    def test_atomic_budget_under_concurrency(self):
        budget = RequestBudget(12)
        with ThreadPoolExecutor(max_workers=24) as pool:
            outcomes = list(pool.map(lambda _: budget.admit(now=200), range(48)))
        self.assertEqual(12, sum(allowed for allowed, _ in outcomes))
        self.assertEqual(36, sum(not allowed for allowed, _ in outcomes))

    def test_validation(self):
        for val in (0, -1, 121, True, 1.2, "12"):
            with self.subTest(value=val), self.assertRaises(ValueError):
                RequestBudget(val)

    def test_flask_search_is_throttled_without_disabling_readiness(self):
        from searx import webapp
        with patch.dict(webapp.settings['goreecloud'],
                        {'request_budget_per_minute': 12}), patch.object(
                webapp.free_search_budget, 'admit', return_value=(False, 7)):
            with webapp.app.test_client() as client:
                response = client.post(
                    '/search',
                    data={'q': 'synthetic'},
                    headers={'Host': 'localhost',
                             'X-Real-IP': '127.0.0.1'},
                )
                self.assertEqual(429, response.status_code)
                self.assertEqual('7', response.headers.get('Retry-After'))
                self.assertNotIn('synthetic', response.get_data(as_text=True))
                self.assertEqual('private, no-store, max-age=0',
                                 response.headers.get('Cache-Control'))
                ready = client.get('/readyz', headers={'Host': 'localhost'})
                self.assertEqual(200, ready.status_code)


if __name__ == '__main__':
    unittest.main()
