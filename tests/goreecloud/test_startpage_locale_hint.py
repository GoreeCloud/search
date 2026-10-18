"""Requested Startpage locale travels with the privacy relay request."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from searx.engines import startpage


class StartpageLocaleTests(unittest.TestCase):
    def test_explicit_browser_locale_sent_to_provider(self):
        for locale, expected in [('en-US','en-US'),('en_US','en-US'),('nl-NL','nl-NL')]:
            with self.subTest(locale=locale), patch.object(startpage, 'get_sc_code', return_value='synthetic'), patch.object(startpage, 'traits', SimpleNamespace(get_region=lambda *a:'en_US', get_language=lambda *a:'english'), create=True), patch.object(startpage, 'CACHE', SimpleNamespace(get=lambda *a:None), create=True), patch.object(startpage, 'logger', SimpleNamespace(debug=lambda *a:None), create=True):
                params = {'headers':{},'cookies':{},'searxng_locale':locale,
                          'safesearch':0,'time_range':None,'pageno':1}
                response = startpage.request('synthetic', params)
                self.assertEqual(expected, response['headers'].get('Accept-Language'))
                self.assertEqual('POST', response['method'])
                self.assertEqual('synthetic', response['data']['query'])
                self.assertIn('preferences', response['cookies'])

    def test_unknown_region_does_not_introduce_unsafe_headers(self):
        with patch.object(startpage, 'get_sc_code', return_value='synthetic'), patch.object(startpage, 'traits', SimpleNamespace(get_region=lambda *a:'en_US', get_language=lambda *a:'english'), create=True), patch.object(startpage, 'CACHE', SimpleNamespace(get=lambda *a:None), create=True), patch.object(startpage, 'logger', SimpleNamespace(debug=lambda *a:None), create=True):
            params = {'headers':{},'cookies':{},'searxng_locale':'all',
                      'safesearch':0,'time_range':None,'pageno':1}
            result = startpage.request('synthetic', params)
            self.assertNotIn('Accept-Language', result['headers'])
