"""Offline security and source-selection contracts for the seven-family federation."""
import unittest
from unittest.mock import patch

from lxml import html

import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch
from searx.engines import goreecloud_ecosia
from searx.goreecloud_policy import (
    BUILTIN_SEARCH_SOURCES, SEARCH_SOURCE_FAMILIES, SEARCH_SOURCE_OPTIONS,
    SearchPolicyViolation, selected_engines_for_category, stored_search_source,
    validate_builtin_sources,
)


class AllSourcesFederationTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}
    families = ('brave', 'startpage', 'qwant', 'duckduckgo', 'ecosia', 'bing', 'google')

    def test_canonical_default_migrates_legacy_all_choice(self):
        self.assertEqual('all', stored_search_source(None))
        self.assertEqual('all', stored_search_source('both'))
        self.assertEqual('all', stored_search_source('non-allowlisted'))
        self.assertEqual('all', stored_search_source('all'))
        self.assertEqual(set(self.families), set(SEARCH_SOURCE_FAMILIES['general']))
        self.assertEqual(24, len(BUILTIN_SEARCH_SOURCES))
        self.assertEqual(7, smoke.settings['goreecloud']['max_provider_fanout'])
        self.assertEqual(SEARCH_SOURCE_OPTIONS['both'], SEARCH_SOURCE_OPTIONS['all'])
        self.assertTrue(smoke.settings['goreecloud']['require_anonymous_egress'])
        self.assertEqual('socks5h://127.0.0.1:9050',
                         smoke.settings['outgoing']['proxies']['all://'])

    def test_category_fanout_and_unavailable_combinations_fail_closed(self):
        self.assertEqual(
            {'general': 7, 'images': 6, 'videos': 5, 'news': 6},
            {name: len(mapping) for name, mapping in SEARCH_SOURCE_FAMILIES.items()},
        )
        for category, mapping in SEARCH_SOURCE_FAMILIES.items():
            self.assertEqual(set(selected_engines_for_category(category).split(',')),
                             set(mapping.values()))
            for family, engine in mapping.items():
                self.assertEqual(engine, selected_engines_for_category(category, family))
        for category in ('images', 'videos', 'news'):
            with self.assertRaises(SearchPolicyViolation):
                selected_engines_for_category(category, 'ecosia')
        with self.assertRaises(SearchPolicyViolation):
            selected_engines_for_category('videos', 'startpage')
        for choice in ('wikipedia', 'google cse', 'duckduckgo weather', 'bing shopping'):
            with self.assertRaises(SearchPolicyViolation):
                validate_builtin_sources([choice], submitted_engines=choice)

    def test_all_sources_default_and_individual_preferences_offline(self):
        expected = sorted(self.families)
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            prefs = client.get('/preferences', headers=self.headers)
            doc = html.fromstring(prefs.data)
            options = doc.xpath('//input[@name="goreecloud_sources"]')
            self.assertEqual(['all'], [o.get('value') for o in options if o.get('checked') is not None])
            self.assertEqual({'all', *self.families}, {o.get('value') for o in options})
            prefs.close()
            for route in ('/preview', '/search'):
                reply = client.post(route, data={'q': 'synthetic', 'format': 'json'}, headers=self.headers)
                self.assertEqual(200, reply.status_code)
                self.assertEqual(expected, reply.json['goreecloud']['selected_engines'])
                reply.close()
            for family in ('duckduckgo', 'ecosia', 'bing', 'google'):
                saved = client.post('/preferences', data={'goreecloud_sources': family},
                                    headers=self.headers)
                self.assertEqual(302, saved.status_code)
                saved.close()
                reply = client.post('/search', data={'q': 'synthetic', 'format': 'json'},
                                    headers=self.headers)
                self.assertEqual(200, reply.status_code)
                self.assertEqual([family], reply.json['goreecloud']['selected_engines'])
                reply.close()
            migrated = client.post('/preferences', data={'goreecloud_sources': 'both'},
                                   headers=self.headers)
            self.assertEqual(302, migrated.status_code)
            migrated.close()
            full = client.post('/search', data={'q': 'synthetic', 'format': 'json'},
                               headers=self.headers)
            self.assertEqual(expected, full.json['goreecloud']['selected_engines'])
            full.close()

    def test_ecosia_url_encoded_and_server_parsing_is_bounded(self):
        params = goreecloud_ecosia.request('privacy & nature', {})
        self.assertEqual('https://www.ecosia.org/search?q=privacy+%26+nature', params['url'])

        class Response:
            def __init__(self, data):
                self.data = data

            def html(self):
                return html.fromstring(self.data)

        fixture = """<html><body>
          <div data-test-id="result">
            <h2><a href="https://example.org/one">First result</a></h2>
            <div class="description">First snippet</div>
          </div>
          <div data-testid="result"><h3><a href="https://example.org/one">Duplicate</a></h3></div>
          <div data-test-id="result"><h2><a href="https://www.ecosia.org/redirect?q=secret">Tracker</a></h2></div>
          <div data-test-id="result"><h2><a href="javascript:alert(1)">Unsafe</a></h2></div>
          <div data-test-id="result"><h2><a href="http://example.org/cleartext">Non-HTTPS</a></h2></div>
        </body></html>"""
        results = goreecloud_ecosia.response(Response(fixture))
        self.assertEqual(1, len(results))
        self.assertEqual('https://example.org/one', results[0].url)
        self.assertEqual('First result', results[0].title)
        self.assertEqual('First snippet', results[0].content)
        self.assertEqual([], list(goreecloud_ecosia.response(Response('<html><body></body></html>'))))

        current_markup = '''<html><body>
            <div data-test-id="mainline-result-ad">
                <a data-test-id="result-link" href="https://ads.example.org/offer">Paid placement</a>
            </div>
            <div data-test-id="mainline-result-web">
                <a data-test-id="result-link" href="https://docs.example.net/source">
                    <span data-test-id="result-title">Search result title</span>
                </a>
                <span data-test-id="result-description">Source description</span>
            </div></body></html>'''
        modern = goreecloud_ecosia.response(Response(current_markup))
        self.assertEqual(1, len(modern))
        self.assertEqual('Search result title', modern[0].title)
        self.assertEqual('https://docs.example.net/source', modern[0].url)
        self.assertEqual('Source description', modern[0].content)


if __name__ == '__main__':
    unittest.main()
