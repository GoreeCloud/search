"""Official 2026-10-11 homepage contract; offline and no provider requests."""
import unittest
from unittest.mock import patch
from lxml import html
import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch


class OfficialHomepageTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_home_has_official_brand_search_benefits_and_footer(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as dispatch:
            reply=client.get('/',headers=self.headers)
            self.assertEqual(200,reply.status_code)
            root=html.fromstring(reply.data)
            self.assertEqual(1,len(root.xpath('//header[contains(@class,"goreecloud-site-header")]')))
            self.assertEqual(1,len(root.xpath('//a[contains(@class,"goreecloud-site-brand")][@href="/"]')))
            self.assertEqual('GoreeCloud Search',' '.join(root.xpath('//h1[@id="goreecloud-home-title"]')[0].text_content().split()))
            self.assertIn('Explore the web. Not your personal data.',root.text_content())
            self.assertEqual(1,len(root.xpath('//div[contains(@class,"goreecloud-mark-hero")]/svg')))
            self.assertEqual(4,len(root.xpath('//ul[contains(@class,"goreecloud-home-benefits")]/li')))
            self.assertEqual(1,len(root.xpath('//section[@id="why-goreecloud-search"]')))
            self.assertIn('Find more. Give away less.',root.text_content())
            self.assertEqual(1,len(root.xpath('//footer[contains(@class,"goreecloud-site-footer")]')))
            self.assertEqual(1,len(root.xpath('//a[@href="/preferences"]')))
            self.assertEqual(1,len(root.xpath('//button[contains(@class,"goreecloud-theme-toggle")]')))
            self.assertEqual(1,len(root.xpath('//body/a[contains(@class,"goreecloud-skip-link")][@href="#goreecloud-content-start"]')))
            self.assertEqual(1,len(root.xpath('//*[@id="goreecloud-content-start"][@tabindex="-1"]')))
            self.assertEqual(1,len(root.xpath('//a[@aria-label="Open source on GitHub"]')))
            self.assertIn('Brave Search and Startpage',root.text_content())
            self.assertIn('not a production privacy guarantee',root.text_content())
            self.assertNotIn('Homepage concept',root.text_content())
            dispatch.assert_not_called()
            reply.close()

    def test_search_and_preview_are_real_post_actions_and_query_free(self):
        with smoke.app.test_client() as client:
            reply=client.get('/',headers=self.headers)
            root=html.fromstring(reply.data)
            forms=root.xpath('//form[@id="search"]')
            self.assertEqual(1,len(forms))
            form=forms[0]
            self.assertEqual('post',form.get('method').lower())
            self.assertEqual('/search',form.get('action'))
            self.assertEqual(1,len(form.xpath('.//input[@name="q"][@type="search"][@aria-keyshortcuts="/"]')))
            self.assertEqual(1,len(form.xpath('.//button[@id="send_search"][@type="submit"]')))
            self.assertEqual(1,len(form.xpath('.//button[@formaction="/preview"][@formmethod="post"]')))
            self.assertEqual(1,len(root.xpath('//a[@href="#why-goreecloud-search"]')))
            self.assertNotIn('q=',reply.get_data(as_text=True))
            self.assertIn('no-store',reply.headers['Cache-Control'])
            reply.close()

    def test_home_one_provider_quick_actions_are_post_only(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            page = client.get('/', headers=self.headers)
            root = html.fromstring(page.data)
            buttons = root.xpath('//form[@id="search"]//button[contains(@class,"goreecloud-home-source")]')
            self.assertEqual(['brave', 'startpage'], [button.get('value') for button in buttons])
            self.assertEqual(['engines', 'engines'], [button.get('name') for button in buttons])
            self.assertEqual(['submit', 'submit'], [button.get('type') for button in buttons])
            self.assertEqual('post', root.xpath('//form[@id="search"]')[0].get('method'))
            self.assertEqual(1, len(root.xpath('//script[contains(@src,"goreecloud-preview.js")]')))
            page.close()

            for source in ('brave', 'startpage'):
                with self.subTest(source=source):
                    response = client.post('/search', data={
                        'q': 'offline single-source request', 'engines': source, 'format': 'json'
                    }, headers=self.headers)
                    self.assertEqual(200, response.status_code)
                    self.assertEqual([source], response.json['goreecloud']['selected_engines'])
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    self.assertNotIn('Location', response.headers)
                    response.close()

    def test_private_assets_are_local_and_style_toggle_is_accessible(self):
        with smoke.app.test_client() as client:
            reply=client.get('/',headers=self.headers)
            root=html.fromstring(reply.data)
            css=root.xpath('//link[contains(@href,"goreecloud-mockup.css")]/@href')
            script=root.xpath('//script[contains(@src,"goreecloud-theme.js")]/@src')
            shortcuts=root.xpath('//script[contains(@src,"goreecloud-shortcuts.js")]/@src')
            self.assertEqual(['/static/themes/simple/goreecloud-mockup.css'],css)
            self.assertEqual(['/static/themes/simple/goreecloud-theme.js'],script)
            self.assertEqual(['/static/themes/simple/goreecloud-shortcuts.js'],shortcuts)
            button=root.xpath('//button[contains(@class,"goreecloud-theme-toggle")]')[0]
            self.assertEqual('false',button.get('aria-pressed'))
            self.assertIn('dark mode',button.get('aria-label'))
            reply.close()
            for path,content_type in ((css[0],'text/css'),(script[0],'javascript'),(shortcuts[0],'javascript')):
                asset=client.get(path,headers=self.headers)
                self.assertEqual(200,asset.status_code)
                self.assertIn(content_type,asset.content_type)
                self.assertNotIn(b'http://',asset.data)
                self.assertNotIn(b'https://',asset.data)
                asset.close()
