"""Offline privacy regression tests for untrusted image-proxy URLs.

The tests never perform network traffic; they verify that unsafe targets
are rejected before upstream requests and that redirects are not followed.
"""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'synthetic-private-image-proxy-test-secret-20261017')

from searx.goreecloud_policy import safe_external_media_url
from searx import settings
from searx.webapp import app
from searx.webutils import new_hmac


class ImageProxyPrivacyTests(unittest.TestCase):
    def test_accepts_public_https_dns_media_targets(self):
        for value in (
            'https://images.example.org/photo.jpg',
            'https://cdn.example.com:443/img.png?size=100&fit=cover',
            'https://xn--bcher-kva.example.org/a.webp',
        ):
            with self.subTest(value=value):
                self.assertTrue(safe_external_media_url(value))

    def test_rejects_local_private_and_ambiguous_hosts(self):
        cases = (
            'http://images.example.org/image.png',
            'https://127.0.0.1/foo.png', 'https://10.0.0.5/',
            'https://192.168.1.1/a', 'https://169.254.169.254/latest/meta-data',
            'https://[::1]/', 'https://[fe80::1]/', 'https://8.8.8.8/a',
            'https://localhost/', 'https://foo.local/', 'https://foo.internal/',
            'https://foo.lan/', 'https://foo.home.arpa/',
            'https://127.1/', 'https://2130706433/', 'https://0x7f000001/',
            'https://images.example.org:8080/img',
            'https://user:password@images.example.org/',
            'https://images.example.org/#fragment',
            'https://images.example.org\\@localhost/',
            'https://images.example.org%2f@localhost/',
            'https://foo..example.org/',
            'https://foo.example.org./',
            'https://images.example.org /a',
            'https://images.example.org/\nfoo',
            'https://images.example.org/' + 'x' * 4097,
            None, 1234, '', '//images.example.org/a',
        )
        for value in cases:
            with self.subTest(value=str(value)[:70]):
                self.assertFalse(safe_external_media_url(value))

    def test_bad_image_url_is_rejected_before_any_network(self):
        target = 'https://127.0.0.1/private-resource'
        signed = new_hmac(settings['server']['secret_key'], target.encode())
        with app.test_client() as client:
            with patch('searx.webapp.http_stream') as request:
                response = client.get('/image_proxy', query_string={'url': target, 'h': signed})
            self.assertEqual(400, response.status_code)
            request.assert_not_called()

    def test_favicon_proxy_remains_disabled_in_private_profile(self):
        # The inherited favicon endpoint must not become a separate SSRF
        # path when the active private profile disables favicon resolution.
        authority = '127.0.0.1'
        signed = new_hmac(settings['server']['secret_key'], authority.encode())
        with app.test_client() as client:
            with patch('searx.favicons.proxy.search_favicon') as fetch:
                response = client.get(
                    '/favicon_proxy',
                    query_string={'authority': authority, 'h': signed},
                )
            self.assertEqual(400, response.status_code)
            fetch.assert_not_called()

    def test_public_looking_url_never_follows_redirects(self):
        target = 'https://images.example.org/safe-looking.png'
        signed = new_hmac(settings['server']['secret_key'], target.encode())
        upstream = SimpleNamespace(
            status_code=302, headers={'Content-Type': 'image/png'},
            close=lambda: None,
        )
        with app.test_client() as client:
            with patch('searx.webapp.http_stream', return_value=(upstream, iter([]))) as request:
                response = client.get('/image_proxy', query_string={'url': target, 'h': signed})
            self.assertEqual(400, response.status_code)
            self.assertIs(False, request.call_args.kwargs['allow_redirects'])
            self.assertEqual(target, request.call_args.kwargs['url'])


if __name__ == '__main__':
    unittest.main()
