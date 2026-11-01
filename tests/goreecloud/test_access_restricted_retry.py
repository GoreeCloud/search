"""Offline UI contract: don't prompt immediate retries against blocked sources."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lxml import html

import test_runtime_smoke as smoke
from test_search_preview import OfflineSearch
from searx.goreecloud_policy import all_selected_sources_access_restricted


RATE_LIMIT = 'searx.exceptions.SearxEngineTooManyRequestsException'
ACCESS_DENIED = 'searx.exceptions.SearxEngineAccessDeniedException'
CAPTCHA = 'searx.exceptions.SearxEngineCaptchaException'
TIMEOUT = 'curl_cffi.requests.exceptions.Timeout'


def error(engine, reason):
    return SimpleNamespace(engine=engine, error_type=reason, suspended=True)


class AllRestrictedSearch(OfflineSearch):
    def search(self):
        response = super().search()
        response.unresponsive_engines = [
            error(name, RATE_LIMIT if name == 'brave' else ACCESS_DENIED)
            for name in sorted({ref.name for ref in self.search_query.engineref_list})
        ]
        return response


class PartialRestrictedSearch(OfflineSearch):
    def search(self):
        response = super().search()
        response.unresponsive_engines = [error('brave', ACCESS_DENIED)]
        return response


class AccessRestrictionRetryTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def test_policy_only_blocks_when_all_selected_report_denial(self):
        self.assertFalse(all_selected_sources_access_restricted([], [error('brave', RATE_LIMIT)]))
        self.assertFalse(all_selected_sources_access_restricted(['brave'], []))
        self.assertFalse(all_selected_sources_access_restricted(['brave'], [error('brave', TIMEOUT)]))
        self.assertFalse(all_selected_sources_access_restricted(
            ['brave', 'startpage'], [error('brave', RATE_LIMIT)]))
        self.assertTrue(all_selected_sources_access_restricted(
            ['brave', 'startpage'], [error('brave', RATE_LIMIT), error('startpage', ACCESS_DENIED)]))
        self.assertTrue(all_selected_sources_access_restricted(['qwant'], [error('qwant', CAPTCHA)]))
        self.assertFalse(all_selected_sources_access_restricted(
            ['brave'], [error('other', RATE_LIMIT)]))

    def test_all_denied_first_page_does_not_offer_same_source_retry(self):
        for engines in ('brave', 'brave,startpage'):
            with self.subTest(engines=engines), smoke.app.test_client() as client, patch(
                'searx.search.SearchWithPlugins', AllRestrictedSearch
            ):
                response = client.post('/search', data={
                    'q': 'synthetic blocked search', 'engines': engines,
                }, headers=self.headers)
                self.assertEqual(200, response.status_code)
                doc = html.fromstring(response.data)
                state = doc.xpath('//section[contains(@class, "goreecloud-empty-state")]')[0]
                self.assertIn('rate-limiting or refusing access', state.text_content())
                self.assertFalse(state.xpath('.//form[contains(@class, "goreecloud-empty-retry")]'))
                self.assertFalse(state.xpath('.//form[contains(@class, "goreecloud-try-startpage")]'))
                self.assertIn('no-store', response.headers['Cache-Control'])
                self.assertEqual('no-referrer', response.headers['Referrer-Policy'])
                self.assertNotIn('Location', response.headers)
                response.close()

    def test_all_denied_later_page_hides_retry_and_previous_requery(self):
        with smoke.app.test_client() as client, patch(
            'searx.search.SearchWithPlugins', AllRestrictedSearch
        ):
            response = client.post('/search', data={
                'q': 'synthetic access refused', 'engines': 'brave,startpage', 'pageno': '3',
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            doc = html.fromstring(response.data)
            state = doc.xpath('//section[contains(@class, "goreecloud-empty-state")]')[0]
            self.assertIn('Wait before retrying this page', state.text_content())
            self.assertFalse(state.xpath('.//form[contains(@class, "goreecloud-empty-retry")]'))
            self.assertEqual(['/'], state.xpath('.//a[contains(text(), "start a new search")]/@href'))
            response.close()

    def test_partial_denial_still_offers_same_selected_source_retry(self):
        with smoke.app.test_client() as client, patch(
            'searx.search.SearchWithPlugins', PartialRestrictedSearch
        ):
            response = client.post('/search', data={
                'q': 'synthetic partial block', 'engines': 'brave,startpage',
            }, headers=self.headers)
            self.assertEqual(200, response.status_code)
            doc = html.fromstring(response.data)
            forms = doc.xpath('//section[contains(@class, "goreecloud-empty-state")]'
                              '//form[contains(@class, "goreecloud-empty-retry")]')
            self.assertEqual(1, len(forms))
            self.assertEqual(
                'brave,startpage', forms[0].xpath('.//input[@name="engines"]/@value')[0])
            self.assertNotIn('q=', forms[0].get('action'))
            response.close()


if __name__ == '__main__':
    unittest.main()
