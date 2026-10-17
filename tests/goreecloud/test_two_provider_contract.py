"""Brave Search and Startpage are GoreeCloud Search's only built-in engines.

All integration checks substitute SearchWithPlugins to prevent provider traffic.
"""
import unittest
from unittest.mock import patch
from lxml import html
import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch
from searx.engines import engines as registered_engines
from searx.goreecloud_policy import BUILTIN_SEARCH_SOURCES, validate_builtin_sources, SearchPolicyViolation


class TwoProviderContractTests(unittest.TestCase):
    headers = {'X-Real-IP':'127.0.0.1'}

    def test_loaded_and_registered_engine_allowlist_is_exact(self):
        configured = smoke.settings['engines']
        self.assertEqual(BUILTIN_SEARCH_SOURCES, {engine['name'] for engine in configured})
        self.assertEqual(BUILTIN_SEARCH_SOURCES, set(registered_engines))
        self.assertEqual(2, len(configured))
        self.assertTrue(all(not engine.get('disabled', False) for engine in configured))
        self.assertTrue(all(not engine.get('inactive', False) for engine in configured))
        self.assertEqual(2, smoke.settings['goreecloud']['max_provider_fanout'])
        self.assertEqual(['general'], list(smoke.settings['categories_as_tabs']))

    def test_home_preferences_and_preview_have_only_two_built_in_sources(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as dispatcher:
            home = client.get('/', headers=self.headers)
            self.assertEqual(200, home.status_code)
            self.assertNotIn(b'category_images', home.data)
            home.close()
            preferences = client.get('/preferences', headers=self.headers)
            self.assertEqual(200, preferences.status_code)
            fields = html.fromstring(preferences.data).xpath('//input[starts-with(@name,"engine_")]/@name')
            self.assertEqual({'engine_brave__general','engine_startpage__general'}, set(fields))
            self.assertEqual(2, len(fields))
            preferences.close()
            preview = client.post('/preview', data={'q':'synthetic source preflight','format':'json'}, headers=self.headers)
            self.assertEqual(200, preview.status_code)
            self.assertEqual(['brave','startpage'], preview.json['goreecloud']['selected_engines'])
            self.assertIs(False, preview.json['goreecloud']['network_requests_made'])
            preview.close()
            dispatcher.assert_not_called()

    def test_unknown_explicit_engine_never_falls_back_to_other_provider(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as dispatcher:
            for engine in ('google','duckduckgo','braveapi','brave.news','startpage news',
                           'brave,startpage,google','', 'BRAVE', 'brave,,startpage'):
                for route in ('/search','/preview'):
                    with self.subTest(engine=engine,route=route):
                        reply = client.post(route, data={'q':'synthetic','engines':engine,'format':'json'},
                                            headers=self.headers)
                        self.assertEqual(422, reply.status_code)
                        self.assertEqual('private_search_policy_violation',
                                         reply.json['goreecloud']['code'])
                        self.assertIn('no-store', reply.headers['Cache-Control'])
                        reply.close()
            dispatcher.assert_not_called()

    def test_each_approved_engine_can_be_selected_without_others(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            for engine in ('brave','startpage'):
                for route in ('/search','/preview'):
                    with self.subTest(engine=engine, route=route):
                        response=client.post(route,data={'q':'synthetic', 'engines':engine, 'format':'json'},
                                             headers=self.headers)
                        self.assertEqual(200,response.status_code)
                        self.assertEqual([engine],response.json['goreecloud']['selected_engines'])
                        response.close()

    def test_unsupported_or_empty_parsed_sources_are_rejected(self):
        for labels in ([], ['brave','google'], ['startpage','brave.images'], ['braveapi']):
            with self.subTest(labels=labels), self.assertRaises(SearchPolicyViolation):
                validate_builtin_sources(labels)
        self.assertEqual(2,validate_builtin_sources(['brave','startpage']))

    def test_only_approved_provider_bangs_are_accepted(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', side_effect=OfflineSearch) as dispatcher:
            for bang, names in (('!br', ['brave']), ('!brave', ['brave']),
                                ('!sp', ['startpage']), ('!startpage', ['startpage']),
                                ('!general', ['brave','startpage'])):
                with self.subTest(approved=bang):
                    reply = client.post('/preview', data={'q':bang+' synthetic', 'format':'json'}, headers=self.headers)
                    self.assertEqual(200,reply.status_code)
                    self.assertEqual(names,reply.json['goreecloud']['selected_engines'])
                    reply.close()
            dispatcher.assert_not_called()
            for rejected in ('!google', '!ddg', '!bing', '!braveapi', '!brave.images',
                             '!!g', '!!unknown', '!news'):
                for route in ('/preview', '/search'):
                    with self.subTest(rejected=rejected,route=route):
                        reply = client.post(route,data={'q': rejected+' synthetic','format':'json'},headers=self.headers)
                        self.assertEqual(422,reply.status_code)
                        self.assertNotIn(rejected,reply.get_data(as_text=True))
                        reply.close()

    def test_explicit_provider_selection_is_not_widened_by_categories(self):
        """The upstream parser unions categories and engines; private mode must not."""
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins', OfflineSearch):
            for provider in ('brave', 'startpage'):
                for route in ('/preview', '/search'):
                    with self.subTest(provider=provider, route=route):
                        response = client.post(route, data={
                            'q': 'synthetic', 'engines': provider,
                            'category_general': '1', 'format': 'json',
                        }, headers=self.headers)
                        self.assertEqual(200, response.status_code)
                        self.assertEqual([provider], response.json['goreecloud']['selected_engines'])
                        response.close()

    def test_conflicting_source_bang_and_engine_choice_fail_closed(self):
        with smoke.app.test_client() as client, patch('searx.search.SearchWithPlugins') as dispatcher:
            for path in ('/preview', '/search'):
                with self.subTest(path=path):
                    response = client.post(path, data={
                        'q': '!br synthetic', 'engines': 'startpage',
                        'category_general': '1', 'format': 'json',
                    }, headers=self.headers)
                    self.assertEqual(422, response.status_code)
                    self.assertNotIn('synthetic', response.get_data(as_text=True))
                    response.close()
            dispatcher.assert_not_called()
