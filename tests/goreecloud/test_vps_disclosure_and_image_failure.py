"""Development deployment disclosure and empty-image regression contracts."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from lxml import html
import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch


ROOT = Path(__file__).resolve().parents[2]


class UnavailableImages(OfflineSearch):
    def search(self):
        answer = super().search()
        answer.unresponsive_engines = [
            SimpleNamespace(engine='startpage images', error_type='TimeoutException', suspended=False)
        ]
        return answer


class VPSDisclosureAndImageFailureTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_homepage_discloses_seven_providers_and_private_vps(self):
        with smoke.app.test_client() as client:
            response = client.get('/', headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertIn(b'Brave Search, Startpage, Qwant, DuckDuckGo, Ecosia, Bing and Google', response.data)
            self.assertIn(b'private VPS Development service', response.data)
            self.assertNotIn(b'local Development build', response.data)
            response.close()

    def test_privacy_page_matches_live_access_model(self):
        with smoke.app.test_client() as client:
            response = client.get('/static/themes/simple/goreecloud/privacy.html', headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertIn(b'search-dev.goreecloud.com', response.data)
            self.assertIn(b'NetBird-only HTTPS', response.data)
            self.assertIn(b'ordinary direct HTTPS', response.data)
            self.assertIn(b'not Tor or a mandatory SOCKS5H relay', response.data)
            self.assertIn(b'12 search submissions per minute', response.data)
            self.assertIn(b'not automatically combined with All Sources', response.data)
            self.assertNotIn(b'External provider requests use a Tor SOCKS5H relay.', response.data)
            self.assertNotIn(b'bound to loopback for local testing', response.data)
            response.close()

    def test_failed_images_explain_source_outage_without_fallback(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', UnavailableImages):
            response = client.post('/search', data={
                'q': 'synthetic image test', 'category_images': '1',
                'engines': 'startpage images',
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            page = html.fromstring(response.data)
            state = page.xpath('//section[contains(@class,"goreecloud-empty-state")]')
            self.assertEqual(1, len(state))
            self.assertIn('No images were returned', state[0].text_content())
            self.assertIn('no replacement provider', state[0].text_content().lower())
            forms = state[0].xpath('.//form[contains(@class,"goreecloud-empty-retry")]')
            self.assertEqual(1, len(forms))
            self.assertEqual('post', forms[0].get('method'))
            self.assertEqual('startpage images', forms[0].xpath('.//input[@name="engines"]/@value')[0])
            response.close()

    def test_failed_image_layout_keeps_details_panel(self):
        css = (ROOT / 'searx/static/themes/simple/goreecloud-settings-categories.css').read_text()
        self.assertIn('#results:has(#urls.goreecloud-image-results .goreecloud-empty-state)', css)
        self.assertIn('grid-template-columns: minmax(0, 1fr) minmax(245px, 285px);', css)
        self.assertIn('max-width: none; box-sizing: border-box;', css)
        self.assertIn('grid-template-columns: minmax(0, 1fr);', css)
        self.assertIn('grid-column: 1; grid-row: 3;', css)
        self.assertNotIn('html[data-glaze-consumer] body.results_endpoint #results:has(#urls.goreecloud-image-results .goreecloud-empty-state)', css)


if __name__ == '__main__':
    unittest.main()
