"""Private GoreeCloud limiter regression tests: no raw IPs or search terms in audit logs/keys."""
import unittest
from ipaddress import ip_network
from unittest.mock import Mock, patch

import test_runtime_smoke as smoke
from flask import request, Response
from searx import limiter, settings
from searx.botdetection import ip_limit, link_token
from searx.botdetection import _helpers


class LimiterPrivacyTests(unittest.TestCase):
    def test_secret_keyed_counter_is_stable_without_retaining_literal_ip(self):
        network = ip_network('198.51.100.0/24')
        with patch.dict(settings['goreecloud'], {'private_search': True}):
            one = ip_limit.counter_network_key(network)
            two = ip_limit.counter_network_key(network)
            three = ip_limit.counter_network_key(ip_network('203.0.113.0/24'))
        self.assertEqual(one, two)
        self.assertNotEqual(one, three)
        self.assertEqual(64, len(one))
        self.assertNotIn('198.51.100', one)
        with patch.dict(settings['goreecloud'], {'private_search': False}):
            self.assertEqual('198.51.100.0/24', ip_limit.counter_network_key(network))

    def test_private_ip_limit_uses_only_keyed_counter_ids(self):
        remote = '198.51.100.11'
        network = ip_network('198.51.100.0/24')
        counter = Mock(return_value=1)
        with smoke.app.test_request_context('/search', method='POST',
                                            data={'q': 'private-query-synthetic'},
                                            environ_base={'REMOTE_ADDR': remote}):
            with patch.dict(settings['goreecloud'], {'private_search': True}):
                with patch('searx.botdetection.ip_limit.valkeydb.get_valkey_client', return_value=Mock()):
                    with patch('searx.botdetection.ip_limit.incr_sliding_window', counter):
                        self.assertIsNone(ip_limit.filter_request(network, request, limiter.get_cfg()))
        self.assertGreaterEqual(counter.call_count, 2)
        for call in counter.call_args_list:
            key = call.args[1]
            self.assertNotIn(remote, key)
            self.assertNotIn('198.51.100', key)
            self.assertNotIn('private-query-synthetic', key)

    def test_private_request_logging_never_serializes_form_or_client_ip(self):
        query = 'not-for-any-log-privacy-marker'
        ip = '198.51.100.29'
        with smoke.app.test_request_context('/search', method='POST',
                                            data={'q': query},
                                            headers={'User-Agent': 'Mozilla/5.0'},
                                            environ_base={'REMOTE_ADDR': ip}):
            with patch.dict(settings['goreecloud'], {'private_search': True}):
                with patch('searx.limiter.logger') as log:
                    with patch('searx.limiter.dump_request',
                               side_effect=AssertionError('Do not serialize private request')):
                        with patch('searx.limiter.ip_lists.pass_ip', return_value=(False, '')):
                            with patch('searx.limiter.ip_lists.block_ip', return_value=(False, '')):
                                for f in ('http_user_agent', 'http_accept', 'http_accept_encoding',
                                          'http_accept_language', 'http_sec_fetch', 'ip_limit'):
                                    with patch('searx.limiter.' + f + '.filter_request', return_value=None):
                                        pass
                                # One shared patched predicate for all filter modules.
                                with patch.multiple(limiter,
                                    http_user_agent=Mock(filter_request=Mock(return_value=None)),
                                    http_accept=Mock(filter_request=Mock(return_value=None)),
                                    http_accept_encoding=Mock(filter_request=Mock(return_value=None)),
                                    http_accept_language=Mock(filter_request=Mock(return_value=None)),
                                    http_sec_fetch=Mock(filter_request=Mock(return_value=None)),
                                    ip_limit=Mock(filter_request=Mock(return_value=None))):
                                    self.assertIsNone(limiter.filter_request(request))
                        seen = str(log.mock_calls)
        self.assertNotIn(query, seen)
        self.assertNotIn(ip, seen)

    def test_blocked_request_and_helper_log_are_private(self):
        ip = '198.51.100.30'
        network = ip_network('198.51.100.0/24')
        with smoke.app.test_request_context('/search', method='POST',
                                            data={'q': 'blocked-private-marker'},
                                            environ_base={'REMOTE_ADDR': ip}):
            with patch.dict(settings['goreecloud'], {'private_search': True}):
                with patch('searx.limiter.logger') as limlog:
                    with patch('searx.limiter.dump_request',
                               side_effect=AssertionError('Do not serialize blocked query')):
                        with patch('searx.limiter.ip_lists.pass_ip', return_value=(False, '')):
                            with patch('searx.limiter.ip_lists.block_ip', return_value=(True, 'blocked')):
                                reply = limiter.filter_request(request)
                        self.assertEqual(429, reply.status_code)
                    self.assertNotIn(ip, str(limlog.mock_calls))
                    self.assertNotIn('blocked-private-marker', str(limlog.mock_calls))
                with patch('searx.botdetection._helpers.logger') as helperlog:
                    reply = _helpers.too_many_requests(network, 'user agent: private-marker')
                    self.assertEqual(429, reply.status_code)
                    self.assertNotIn('198.51.100', str(helperlog.mock_calls))
                    self.assertNotIn('private-marker', str(helperlog.mock_calls))

    def test_ping_challenge_logging_hides_network_and_token_key(self):
        ip = '198.51.100.31'
        with smoke.app.test_request_context('/search', method='POST',
                                            environ_base={'REMOTE_ADDR': ip}):
            with patch.dict(settings['goreecloud'], {'private_search': True}):
                with patch('searx.botdetection.link_token.valkeydb.get_valkey_client') as valkey:
                    valkey.return_value.get.return_value = None
                    with patch('searx.botdetection.link_token.logger') as log:
                        self.assertTrue(link_token.is_suspicious(ip_network('198.51.100.0/24'), request))
                    seen = str(log.mock_calls)
        self.assertNotIn('198.51.100', seen)
        self.assertNotIn('SearXNG_limiter.ping', seen)


if __name__ == '__main__':
    unittest.main()
