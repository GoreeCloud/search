"""GoreeCloud Search's three approved provider families and local UI."""
import unittest
from unittest.mock import patch
from lxml import html
import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch
from searx.goreecloud_policy import selected_engines_for_category, stored_search_source


class QwantIntegrationTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_all_three_are_allowed_and_none_is_default_safesearch(self):
        self.assertEqual(0, smoke.settings['search']['safe_search'])
        self.assertEqual(7, smoke.settings['goreecloud']['max_provider_fanout'])
        self.assertEqual('all', stored_search_source(None))
        for category, expected in (
            ('general', 'brave,startpage,qwant,duckduckgo,ecosia,bing,google'),
            ('images', 'brave.images,startpage images,qwant images,duckduckgo images,bing images,google images'),
            ('videos', 'brave.videos,qwant videos,duckduckgo videos,bing videos,google videos'),
            ('news', 'brave.news,startpage news,qwant news,duckduckgo news,bing news,google news'),
        ):
            with self.subTest(category=category):
                self.assertEqual(expected, selected_engines_for_category(category))

    def test_default_and_qwant_only_dispatch_offline(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            first = client.post('/search', data={'q': 'synthetic', 'format': 'json'}, headers=self.headers)
            self.assertEqual(200, first.status_code)
            self.assertEqual(['bing', 'brave', 'duckduckgo', 'ecosia', 'google', 'qwant', 'startpage'], first.json['goreecloud']['selected_engines'])
            first.close()
            pref = client.post('/preferences', data={'goreecloud_sources': 'qwant', 'preferences': ''}, headers=self.headers)
            self.assertEqual(302, pref.status_code)
            pref.close()
            for category, expected in [('general', 'qwant'), ('images', 'qwant images'),
                                       ('videos', 'qwant videos'), ('news', 'qwant news')]:
                with self.subTest(category=category):
                    data = {'q': 'synthetic', 'format': 'json', 'category_' + category: '1'}
                    reply = client.post('/search', data=data, headers=self.headers)
                    self.assertEqual(200, reply.status_code)
                    self.assertEqual([expected], reply.json['goreecloud']['selected_engines'])
                    reply.close()

    def test_branded_pages_and_media_grid_contract(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            about = client.get('/info/en/about', headers=self.headers)
            self.assertEqual(200, about.status_code)
            self.assertIn(b'About GoreeCloud Search', about.data)
            self.assertNotIn(b'<h1>About SearXNG</h1>', about.data)
            about.close()
            privacy = client.get('/static/themes/simple/goreecloud/privacy.html', headers=self.headers)
            self.assertEqual(200, privacy.status_code)
            self.assertIn(b'Privacy and sources', privacy.data)
            self.assertIn(b'Qwant', privacy.data)
            privacy.close()
            images = client.post('/search', data={'q': 'synthetic','category_images':'1'}, headers=self.headers)
            self.assertEqual(200, images.status_code)
            node = html.fromstring(images.data).xpath('//*[@id="urls"]')
            self.assertEqual(1, len(node))
            self.assertIn('goreecloud-image-results', node[0].get('class', ''))
            images.close()


if __name__ == '__main__':
    unittest.main()
