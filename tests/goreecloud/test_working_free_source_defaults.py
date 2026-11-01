"""Offline regression for no-cost, tested-source Development defaults.

Current provider availability is not guaranteed by a historic smoke result.
The existing seven-family allowlist remains intact and user-selectable.
"""
from pathlib import Path
import unittest
from unittest.mock import patch
import yaml
from lxml import html

import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch
from searx.goreecloud_policy import (
    WORKING_FREE_SOURCE_FAMILIES, SEARCH_SOURCE_FAMILIES, SEARCH_SOURCE_OPTIONS,
    selected_engines_for_category, requested_search_source, stored_search_source,
)

ROOT = Path(__file__).resolve().parents[2]
FREE = ROOT / 'configs/goreecloud/settings.free-first.yml'


class WorkingFreeSourcesTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_no_cost_profile_is_opt_in_and_existing_private_profile_unchanged(self):
        free = yaml.safe_load(FREE.read_text())
        private = yaml.safe_load((ROOT / 'configs/goreecloud/settings.yml').read_text())
        self.assertEqual('working', free['goreecloud']['default_source_choice'])
        self.assertNotIn('default_source_choice', private['goreecloud'])
        self.assertFalse(free['goreecloud']['require_anonymous_egress'])
        self.assertTrue(private['goreecloud']['require_anonymous_egress'])
        self.assertEqual(7, len(SEARCH_SOURCE_FAMILIES['general']))

    def test_per_category_working_sources_are_real_allowlisted_adapters(self):
        expected = {
            'general': 'duckduckgo,bing,startpage',
            'images': 'bing images',
            'videos': 'duckduckgo videos,bing videos',
            'news': 'duckduckgo news',
        }
        for cat, choices in WORKING_FREE_SOURCE_FAMILIES.items():
            with self.subTest(category=cat):
                self.assertEqual(expected[cat], selected_engines_for_category(cat, 'working'))
                self.assertTrue(all(
                    member in SEARCH_SOURCE_FAMILIES[cat] for member in choices
                ))
        self.assertEqual(expected['general'], SEARCH_SOURCE_OPTIONS['working'])
        self.assertEqual(
            'brave,startpage,qwant,duckduckgo,ecosia,bing,google',
            selected_engines_for_category('general', 'all'),
        )

    def test_source_preference_priority_and_legacy_cookie_are_preserved(self):
        self.assertEqual('working', stored_search_source(None, default='working'))
        self.assertEqual('working', stored_search_source('not-valid', default='working'))
        self.assertEqual('all', stored_search_source('all', default='working'))
        self.assertEqual('all', stored_search_source(None))
        self.assertEqual('all', stored_search_source('both', default='working'))
        self.assertEqual('duckduckgo,bing,startpage', requested_search_source(
            explicit=None, stored=None, query_specific=False,
            default='working', category='general',
        ))
        self.assertEqual('bing images', requested_search_source(
            explicit=None, stored=None, query_specific=False,
            default='working', category='images',
        ))
        self.assertEqual('google', requested_search_source(
            explicit='google', stored=None, query_specific=False,
            default='working', category='general',
        ))
        self.assertIsNone(requested_search_source(
            explicit=None, stored=None, query_specific=True,
            default='working', category='general',
        ))
        self.assertIsNone(requested_search_source(
            explicit=None, stored=None, query_specific=False,
            default='all', category='general',
        ))

    def test_fresh_browser_uses_working_preset_and_saved_all_stays_all(self):
        with patch.dict(smoke.settings['goreecloud'], {'default_source_choice': 'working'}):
            with smoke.app.test_client() as client, patch(
                'searx.search.SearchWithPlugins', OfflineSearch
            ):
                pref = client.get('/preferences', headers=self.headers)
                doc = html.fromstring(pref.data)
                chosen = doc.xpath('//input[@name="goreecloud_sources"][@checked]/@value')
                self.assertEqual(['working'], chosen)
                pref.close()
                for category, selected in (
                    ('general', ['bing', 'duckduckgo', 'startpage']),
                    ('images', ['bing images']),
                    ('videos', ['bing videos', 'duckduckgo videos']),
                    ('news', ['duckduckgo news']),
                ):
                    with self.subTest(category=category):
                        search = client.post('/search', data={
                            'q': 'synthetic', 'format': 'json', 'category_'+category: '1',
                        }, headers=self.headers)
                        self.assertEqual(200, search.status_code)
                        self.assertEqual(selected, search.json['goreecloud']['selected_engines'])
                        search.close()
                pref = client.post('/preferences', data={
                    'goreecloud_sources': 'all', 'preferences': '',
                }, headers=self.headers)
                self.assertEqual(302, pref.status_code)
                pref.close()
                search = client.post('/search', data={
                    'q': 'synthetic', 'format': 'json',
                }, headers=self.headers)
                self.assertEqual(
                    ['bing','brave','duckduckgo','ecosia','google','qwant','startpage'],
                    search.json['goreecloud']['selected_engines']
                )
                search.close()


if __name__ == '__main__':
    unittest.main()
