"""Category tabs only dispatch to the two approved provider families.

Offline synthetic results; no provider HTTP request.
"""
import unittest
from unittest.mock import patch

from lxml import html

import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch
from searx.goreecloud_policy import (
    selected_engines_for_category, SearchPolicyViolation, BUILTIN_SEARCH_SOURCES,
)


class CategoryNavigationTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_family_routes_only_to_approved_variant_instances(self):
        expected = {
            'general': 'brave,startpage',
            'images': 'brave.images,startpage images',
            'videos': 'brave.videos',
            'news': 'brave.news,startpage news',
        }
        for category, mapping in expected.items():
            with self.subTest(category=category):
                self.assertEqual(mapping, selected_engines_for_category(category))
                self.assertTrue(set(mapping.split(',')).issubset(BUILTIN_SEARCH_SOURCES))
        self.assertEqual('brave.videos', selected_engines_for_category('videos', 'brave'))
        for category, choice in [('videos', 'startpage'), ('maps', 'both'), ('images', 'google')]:
            with self.subTest(category=category, choice=choice):
                with self.assertRaises(SearchPolicyViolation):
                    selected_engines_for_category(category, choice)

    def test_navigation_forms_use_post_and_correct_engines(self):
        with smoke.app.test_client() as client, patch(
            'searx.search.SearchWithPlugins', OfflineSearch
        ):
            response = client.post('/search', data={'q': 'synthetic category test'}, headers=self.headers)
            self.assertEqual(200, response.status_code)
            doc = html.fromstring(response.data)
            forms = doc.xpath('//nav[contains(@class,"goreecloud-category-tabs")]/form')
            self.assertEqual(4, len(forms))
            actual = {}
            for form in forms:
                self.assertEqual('post', form.get('method'))
                self.assertEqual('/search', form.get('action'))
                hidden = {e.get('name'): e.get('value') for e in form.xpath('./input')}
                self.assertEqual('synthetic category test', hidden['q'])
                self.assertEqual(1, len([key for key in hidden if key.startswith('category_')]))
                category = next(key.replace('category_', '') for key in hidden if key.startswith('category_'))
                actual[category] = hidden['engines']
                self.assertEqual('', form.get('action').split('?', 1)[-1] if '?' in form.get('action') else '')
            self.assertEqual({
                'general': 'brave,startpage', 'images': 'brave.images,startpage images',
                'videos': 'brave.videos', 'news': 'brave.news,startpage news',
            }, actual)
            response.close()

    def test_offline_category_post_dispatch_and_startpage_video_limitation(self):
        with smoke.app.test_client() as client, patch(
            'searx.search.SearchWithPlugins', OfflineSearch
        ):
            for category, selected in [
                ('images', ['brave.images', 'startpage images']),
                ('videos', ['brave.videos']),
                ('news', ['brave.news', 'startpage news']),
            ]:
                with self.subTest(category=category):
                    response = client.post('/search', data={
                        'q': 'synthetic category',
                        'category_' + category: '1', 'format': 'json',
                    }, headers=self.headers)
                    self.assertEqual(200, response.status_code)
                    self.assertEqual(selected, response.json['goreecloud']['selected_engines'])
                    response.close()
            saved = client.post('/preferences', data={
                'goreecloud_sources': 'startpage', 'preferences': '',
            }, headers=self.headers)
            self.assertEqual(302, saved.status_code)
            saved.close()
            response = client.post('/search', data={
                'q': 'synthetic', 'category_videos': '1', 'format': 'json',
            }, headers=self.headers)
            self.assertEqual(422, response.status_code)
            response.close()
            response = client.post('/search', data={
                'q': 'synthetic', 'category_news': '1', 'format': 'json',
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertEqual(['startpage news'], response.json['goreecloud']['selected_engines'])
            response.close()
            html_response = client.post('/search', data={
                'q': 'synthetic', 'category_news': '1',
            }, headers=self.headers)
            self.assertEqual(200, html_response.status_code)
            doc = html.fromstring(html_response.data)
            self.assertFalse(doc.xpath('//nav[contains(@class,"goreecloud-category-tabs")]//form[.//button[normalize-space()="Videos"]]'))
            disabled = doc.xpath('//nav[contains(@class,"goreecloud-category-tabs")]//span[@aria-disabled="true"]')
            self.assertEqual(1, len(disabled))
            self.assertIn('Videos', disabled[0].text_content())
            html_response.close()


if __name__ == '__main__':
    unittest.main()
