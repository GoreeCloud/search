"""Saved, allowlisted Search source selection without homepage clutter or egress."""
import unittest
from unittest.mock import patch
from lxml import html

import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch
from searx.goreecloud_policy import requested_search_source, stored_search_source


class BrowserLocalSearchSourcesTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_cookie_values_are_allowlisted_and_explicit_selection_wins(self):
        self.assertEqual('all', stored_search_source(None))
        self.assertEqual('all', stored_search_source('unknown,extra'))
        self.assertEqual('brave', stored_search_source('brave'))
        self.assertEqual('startpage', stored_search_source('startpage'))
        self.assertEqual('brave', requested_search_source(
            explicit='brave', stored='startpage', query_specific=False,
        ))
        self.assertIsNone(requested_search_source(
            explicit=None, stored='brave', query_specific=True,
        ))
        self.assertEqual('brave,startpage,qwant,duckduckgo,ecosia,bing,google', requested_search_source(
            explicit=None, stored='both', query_specific=False,
        ))

    def test_home_has_no_provider_switches_and_settings_has_three_choices(self):
        with smoke.app.test_client() as client:
            home = client.get('/', headers=self.headers)
            root = html.fromstring(home.data)
            self.assertFalse(root.xpath('//form[@id="search"]//button[@name="engines"]'))
            self.assertFalse(root.xpath('//form[@id="search"]//button[@formaction="/preview"]'))
            self.assertTrue(root.xpath('//a[@href="/preferences"]'))
            home.close()
            page = client.get('/preferences', headers=self.headers)
            self.assertEqual(200, page.status_code)
            doc = html.fromstring(page.data)
            radios = doc.xpath('//input[@type="radio"][@name="goreecloud_sources"]')
            self.assertEqual(['all', 'brave', 'startpage', 'qwant', 'duckduckgo', 'ecosia', 'bing', 'google'], [radio.get('value') for radio in radios])
            self.assertEqual(['all'], [radio.get('value') for radio in radios if radio.get('checked') is not None])
            page.close()

    def test_preference_cookie_persists_and_selects_only_approved_sources(self):
        with smoke.app.test_client() as client, patch(
            'searx.search.SearchWithPlugins', OfflineSearch
        ) as executor:
            for value, expected in (
                ('brave', ['brave']),
                ('startpage', ['startpage']),
                ('qwant', ['qwant']),
                ('all', ['bing', 'brave', 'duckduckgo', 'ecosia', 'google', 'qwant', 'startpage']),
            ):
                with self.subTest(value=value):
                    saved = client.post('/preferences', data={
                        'goreecloud_sources': value,
                        'preferences': '',  # Stock Preferences page includes this optional field.
                    }, headers=self.headers)
                    self.assertEqual(302, saved.status_code)
                    cookies = saved.headers.getlist('Set-Cookie')
                    chosen = [c for c in cookies if c.startswith('goreecloud_search_sources=')]
                    self.assertEqual(1, len(chosen))
                    self.assertIn('HttpOnly', chosen[0])
                    self.assertIn('SameSite=Lax', chosen[0])
                    saved.close()
                    response = client.post('/search', data={
                        'q': 'synthetic preferences verification', 'format': 'json',
                    }, headers=self.headers)
                    self.assertEqual(200, response.status_code)
                    self.assertEqual(expected, response.json['goreecloud']['selected_engines'])
                    response.close()
            # The offline stub deliberately issues no provider network requests.

    def test_invalid_preference_rejected_without_cookie_mutation(self):
        with smoke.app.test_client() as client:
            response = client.post('/preferences', data={
                'goreecloud_sources': 'unknown',
            }, headers=self.headers)
            self.assertEqual(422, response.status_code)
            self.assertFalse(any('goreecloud_search_sources=' in cookie
                                 for cookie in response.headers.getlist('Set-Cookie')))
            response.close()

    def test_serialized_preference_import_stays_blocked_while_empty_optional_field_is_allowed(self):
        with smoke.app.test_client() as client:
            ordinary = client.post('/preferences', data={
                'goreecloud_sources': 'brave', 'preferences': '',
            }, headers=self.headers)
            self.assertEqual(302, ordinary.status_code)
            ordinary.close()
            for method, target, data in (
                ('POST', '/preferences', {'goreecloud_sources': 'brave', 'preferences': 'unsafe-data'}),
                ('GET', '/preferences?preferences=unsafe-data', None),
            ):
                with self.subTest(method=method):
                    response = client.open(target, method=method, data=data, headers=self.headers)
                    self.assertEqual(422, response.status_code)
                    self.assertFalse(any('goreecloud_search_sources=' in value
                                         for value in response.headers.getlist('Set-Cookie')))
                    response.close()


if __name__ == '__main__':
    unittest.main()
