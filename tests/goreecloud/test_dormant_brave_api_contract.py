"""Offline tests only: Brave API adapter stays inactive in private GoreeCloud."""
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from searx.engines import braveapi
from searx.exceptions import SearxEngineAPIException
from searx.goreecloud_policy import BUILTIN_SEARCH_SOURCES
from searx.result_types import MainResult


def args():
    return {'pageno': 1, 'time_range': None, 'safesearch': 1,
            'headers': {}, 'url': '', 'json': {}, 'method': 'GET',
            'allow_redirects': True}


class Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class DormantBraveApiTests(unittest.TestCase):
    def test_missing_key_and_unapproved_adapter(self):
        self.assertNotIn('braveapi', BUILTIN_SEARCH_SOURCES)
        self.assertEqual('', braveapi.api_key)
        with self.assertRaises(SearxEngineAPIException):
            braveapi.request('offline test', args())

    def test_private_config_keeps_api_inactive(self):
        root = Path(__file__).resolve().parents[2]
        defaults = yaml.safe_load((root / 'searx/settings.yml').read_text())
        engine = next(item for item in defaults['engines'] if item['name'] == 'braveapi')
        self.assertIs(True, engine['inactive'])
        self.assertEqual('', engine['api_key'])
        profile = yaml.safe_load((root / 'configs/goreecloud/settings.yml').read_text())
        self.assertNotIn('braveapi', profile['use_default_settings']['engines']['keep_only'])
        self.assertFalse(any(item.get('name') == 'braveapi' for item in profile['engines']))

    def test_post_has_no_query_in_url(self):
        with patch.object(braveapi, 'api_key', 'offline-placeholder'):
            p = args()
            braveapi.request('offline query', p)
            self.assertEqual('POST', p['method'])
            self.assertEqual(braveapi.base_url, p['url'])
            self.assertNotIn('offline query', p['url'])
            self.assertEqual('offline query', p['json']['q'])
            self.assertEqual('web', p['json']['result_filter'])
            self.assertIs(False, p['allow_redirects'])
            self.assertEqual('offline-placeholder', p['headers']['X-Subscription-Token'])

    def test_freshness_and_pagination_bounds(self):
        with patch.object(braveapi, 'api_key', 'offline-placeholder'):
            for period, expected in braveapi.time_range_map.items():
                p = args()
                p.update(pageno=10, time_range=period)
                braveapi.request('offline', p)
                self.assertEqual(9, p['json']['offset'])
                self.assertEqual(expected, p['json']['freshness'])
            for page in (0, 11, -1, True):
                p = args()
                p['pageno'] = page
                with self.assertRaises(SearxEngineAPIException):
                    braveapi.request('offline', p)

    def test_wrong_endpoint_count_or_query_rejected(self):
        with patch.object(braveapi, 'api_key', 'offline-placeholder'):
            with patch.object(braveapi, 'base_url', 'https://elsewhere.invalid/'):
                with self.assertRaises(SearxEngineAPIException):
                    braveapi.request('offline', args())
            with patch.object(braveapi, 'results_per_page', 21):
                with self.assertRaises(SearxEngineAPIException):
                    braveapi.request('offline', args())
            for query in ('', ' ', 'word ' * 76, 'x' * 601):
                with self.assertRaises(SearxEngineAPIException):
                    braveapi.request(query, args())

    def test_web_results_use_main_result(self):
        results = braveapi.response(Response({'web': {'results': [{
            'url': 'https://example.org/article', 'title': 'Article',
            'description': 'Description'
        }]}}))
        rows = list(results)
        self.assertEqual(1, len(rows))
        self.assertIsInstance(rows[0], MainResult)
        self.assertEqual('Article', rows[0].title)
        self.assertEqual('Description', rows[0].content)

    def test_bad_results_fail_closed(self):
        for item in ({}, {'web': None}, {'web': {'results': None}},
                     {'web': {'results': [42]}},
                     {'web': {'results': [{'url': 'https://x.example',
                                          'title': ''}]}}):
            with self.assertRaises(SearxEngineAPIException):
                braveapi.response(Response(item))
        for url in ('http://example.org/plain', 'https://localhost/private',
                    'https://user:pass@example.org', 'https://example.invalid/home'):
            with self.assertRaises(SearxEngineAPIException):
                braveapi.response(Response({'web': {'results': [
                    {'url': url, 'title': 'Unsafe'}]}}))
        self.assertEqual([], list(braveapi.response(
            Response({'web': {'results': []}}))))


if __name__ == '__main__':
    unittest.main()
