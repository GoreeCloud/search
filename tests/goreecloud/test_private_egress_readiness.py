"""Offline privacy readiness gate for GoreeCloud Search.

Readiness reports configuration acceptance only, never verified provider access,
remote visitor IP masking, gateway availability, or a DNS-rebinding firewall.
"""
import os
import unittest
from unittest.mock import patch

import test_runtime_smoke as smoke
from searx.network.network import NETWORKS, Network


class PrivateReadinessEgressTests(unittest.TestCase):
    headers = {'X-Real-IP': '127.0.0.1'}

    def _ready(self, candidates):
        with patch.dict(NETWORKS, candidates, clear=True):
            with smoke.app.test_client() as client:
                response = client.get('/readyz', headers=self.headers)
                result = (response.status_code, response.data, response.headers)
                response.close()
                return result

    def _gateway(self, proxy='socks5h://127.0.0.1:9050', **overrides):
        values = dict(
            enable_http=False, verify=True, enable_http3=False,
            proxies={'all://': proxy},
            privacy_proxy_required=True, privacy_egress_mode='gateway',
        )
        values.update(overrides)
        return Network(**values)

    def _hosted(self, **overrides):
        values = dict(
            enable_http=False, verify=True, enable_http3=False, proxies={},
            privacy_proxy_required=True, privacy_egress_mode='server_masked',
            server_masked_acknowledged=True,
        )
        values.update(overrides)
        return Network(**values)

    def test_valid_non_tor_gateway_configuration_is_ready_without_network_access(self):
        with patch('searx.network.network.new_client') as new_client:
            code, body, headers = self._ready({'__DEFAULT__': self._gateway()})
        self.assertEqual((200, b'READY'), (code, body))
        self.assertIn('no-store', headers['Cache-Control'])
        new_client.assert_not_called()

    def test_gateway_readiness_rejects_invalid_proxy_configurations(self):
        scenarios = (
            self._gateway('http://127.0.0.1:9050'),
            self._gateway('socks5h://10.10.10.10:9050'),
            self._gateway('socks5h://127.0.0.1:9050', verify=False),
            self._gateway('socks5h://127.0.0.1:9050', enable_http=True),
            self._gateway('socks5h://127.0.0.1:9050', enable_http3=True),
            self._gateway('socks5h://127.0.0.1:9050', privacy_egress_mode='unknown'),
            self._gateway('socks5h://127.0.0.1:9050', proxies={}),
            self._gateway('socks5h://127.0.0.1:9050',
                          proxies={'all://': ['socks5h://127.0.0.1:9050',
                                              'http://127.0.0.1:9051']}),
        )
        with patch('searx.network.network.new_client') as new_client:
            for i, candidate in enumerate(scenarios):
                with self.subTest(case=i):
                    code, body, _ = self._ready({'__DEFAULT__': candidate})
                    self.assertEqual((503, b'NOT_READY'), (code, body))
        new_client.assert_not_called()

    def test_server_masking_requires_both_explicit_opt_ins(self):
        hosted = self._hosted()
        with patch('searx.network.network.new_client') as new_client:
            with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '0'}):
                self.assertEqual((503, b'NOT_READY'), self._ready(
                    {'__DEFAULT__': hosted})[:2])
            with patch.dict(os.environ, {'GOREECLOUD_SERVER_MASKED_EGRESS': '1'}):
                self.assertEqual((200, b'READY'), self._ready(
                    {'__DEFAULT__': hosted})[:2])
                self.assertEqual((503, b'NOT_READY'), self._ready(
                    {'__DEFAULT__': self._hosted(server_masked_acknowledged=False)})[:2])
                self.assertEqual((503, b'NOT_READY'), self._ready(
                    {'__DEFAULT__': self._hosted(using_tor_proxy=True)})[:2])
                self.assertEqual((503, b'NOT_READY'), self._ready(
                    {'__DEFAULT__': self._hosted(proxies={'all://': 'socks5h://127.0.0.1:9050'})})[:2])
        new_client.assert_not_called()

    def test_all_registered_networks_must_be_privacy_guarded(self):
        valid = self._gateway()
        for invalid in (
            Network(enable_http=False, proxies={}, privacy_proxy_required=False),
            self._gateway('socks5h://127.0.0.1:9050', verify=False),
        ):
            with self.subTest(invalid=invalid):
                self.assertEqual((503, b'NOT_READY'), self._ready({
                    '__DEFAULT__': valid,
                    'brave': invalid,
                })[:2])

    def test_brave_engine_http3_override_cannot_disable_private_egress(self):
        # The real Brave engine modules ask for HTTP/3, but private Search
        # must initialize their named networks with HTTP/3 disabled.
        for name in ('brave', 'brave.images', 'brave.videos', 'brave.news'):
            with self.subTest(engine=name):
                self.assertIn(name, NETWORKS)
                self.assertTrue(NETWORKS[name].privacy_proxy_required)
                self.assertFalse(NETWORKS[name].enable_http3)
                self.assertTrue(NETWORKS[name].private_egress_configured())

    def test_absent_network_registry_fails_closed(self):
        self.assertEqual((503, b'NOT_READY'), self._ready({})[:2])


if __name__ == '__main__':
    unittest.main()
