"""Fail-closed direct-HTTPS Search provider transport tests (no network IO)."""

import asyncio
import os
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-free-guard-tests-only-000000000')

import yaml
from curl_cffi.requests.exceptions import ProxyError

from searx.network.network import Network


def free_network():
    return Network(
        enable_http=False,
        verify=True,
        proxies={},
        using_tor_proxy=False,
        privacy_proxy_required=False,
        provider_target_guard_required=True,
    )


class FreeProviderEgressGuardTests(unittest.TestCase):
    def test_free_profile_enables_guard_without_requiring_tor(self):
        profile = yaml.safe_load(
            (ROOT / 'configs/goreecloud/settings.free-first.yml').read_text(encoding='utf-8')
        )
        self.assertTrue(profile['goreecloud']['private_search'])
        self.assertFalse(profile['goreecloud']['require_anonymous_egress'])
        self.assertFalse(profile['outgoing']['using_tor_proxy'])
        self.assertEqual({}, profile['outgoing']['proxies'])
        net = free_network()
        self.assertTrue(net.provider_target_guard_required)
        self.assertFalse(net.privacy_proxy_required)

    def test_real_free_profile_initializes_all_networks_with_guard(self):
        # A fresh interpreter avoids the private-profile global settings used
        # by the rest of the offline Search regression tests.
        code = (
            'from searx.network.network import NETWORKS, initialize; '
            'initialize(); '
            'assert NETWORKS; '
            'assert all(n.provider_target_guard_required for n in NETWORKS.values()); '
            'assert not any(n.privacy_proxy_required for n in NETWORKS.values())'
        )
        env = dict(os.environ)
        env['SEARXNG_SETTINGS_PATH'] = str(ROOT / 'configs/goreecloud/settings.free-first.yml')
        env['SEARXNG_SECRET'] = 'goreecloud-free-profile-validation-only-000000000'
        result = subprocess.run(
            [sys.executable, '-c', code],
            cwd=ROOT, env=env, text=True, capture_output=True,
            timeout=20, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr[-1500:])

    def test_hostile_targets_and_request_overrides_block_before_client(self):
        targets = (
            'http://search.example.org/',
            'https://localhost/', 'https://127.0.0.1/',
            'https://[::1]/', 'https://169.254.169.254/latest/meta-data/',
            'https://metadata.google.internal/', 'https://host.local/',
            'https://user:pass@search.example.org/',
            'https://search.example.org:8443/',
            'https://search.example.org\\@169.254.169.254/',
        )
        with patch('searx.network.network.new_client') as factory:
            for url in targets:
                with self.subTest(url=url), self.assertRaises(ProxyError):
                    asyncio.run(free_network().request('GET', url))
            for kwargs in (
                {'proxy': 'http://localhost:8080'},
                {'proxies': {'all://': 'http://localhost:8080'}},
                {'interface': '127.0.0.1'},
                {'curl_options': {1: 1}},
            ):
                with self.subTest(kwargs=kwargs), self.assertRaises(ProxyError):
                    asyncio.run(free_network().request(
                        'GET', 'https://search.example.org/', **kwargs
                    ))
            factory.assert_not_called()

    def test_tls_and_client_override_cannot_disable_guard(self):
        net = free_network()
        with patch('searx.network.network.new_client') as factory:
            with self.assertRaises(ProxyError):
                asyncio.run(net.get_client(verify=False))
            with self.assertRaises(ProxyError):
                asyncio.run(net.get_client(curl_options={1: 1}))
            factory.assert_not_called()

    def test_redirect_responses_never_trigger_automatic_next_hop(self):
        for status in (301, 302, 307, 308):
            with self.subTest(status=status):
                net = free_network()
                client = Mock(is_closed=False)
                client.request = AsyncMock(return_value=SimpleNamespace(status_code=status))
                client.stream = Mock(return_value='synthetic-stream')
                with patch('searx.network.network.new_client', return_value=client):
                    response = asyncio.run(net.request(
                        'GET', 'https://search.example.org/path',
                        allow_redirects=True,
                        headers={
                            'X-Forwarded-For': '192.0.2.1',
                            'Cookie': 'private-value',
                            'Authorization': 'Bearer redacted',
                            'Accept': 'application/json',
                        },
                        cookies={'session': 'private-value'},
                        raise_for_httperror=False,
                    ))
                    self.assertEqual(status, response.status_code)
                    self.assertEqual('synthetic-stream', asyncio.run(
                        net.stream('GET', 'https://search.example.org/path',
                                   allow_redirects=True)
                    ))
                call = client.request.call_args
                self.assertIs(False, call.kwargs['allow_redirects'])
                self.assertEqual({'Accept': 'application/json'}, call.kwargs['headers'])
                self.assertNotIn('cookies', call.kwargs)
                self.assertIs(False, client.stream.call_args.kwargs['allow_redirects'])


if __name__ == '__main__':
    unittest.main()
