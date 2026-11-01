"""Offline image-proxy target and byte-boundary regressions."""

import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-image-proxy-tests-only-0000000000')

import test_runtime_smoke as smoke
from searx import webapp


class ImageProxyBoundsTests(unittest.TestCase):
    def test_stream_has_actual_byte_limit_and_closes_on_overflow(self):
        closed = Mock()
        stream = webapp._bounded_image_proxy_stream(
            iter((b'abc', b'defg', b'overflow')), 7, closed
        )
        self.assertEqual([b'abc', b'defg'], list(stream))
        closed.assert_called_once()

    def test_rejects_invalid_chunks_and_closes(self):
        closed = Mock()
        self.assertEqual(
            [],
            list(webapp._bounded_image_proxy_stream(iter((None,)), 7, closed)),
        )
        closed.assert_called_once()

    def test_hmac_does_not_authorize_local_or_malformed_media_targets(self):
        hostile = (
            'http://images.example.org/image.png',
            'https://127.0.0.1/internal.png',
            'https://169.254.169.254/latest/meta-data',
            'https://localhost/image.png',
            'https://user:pass@images.example.org/image.png',
            'https://images.example.org:8443/image.png',
        )
        with (
            smoke.app.test_client() as client,
            patch.object(webapp, 'is_hmac_of', return_value=True),
            patch.object(webapp, 'http_stream') as fetch,
        ):
            for url in hostile:
                with self.subTest(url=url):
                    response = client.get('/image_proxy?' + urlencode({'url': url, 'h': 'synthetic'}))
                    self.assertEqual(400, response.status_code)
            fetch.assert_not_called()

    def test_signed_https_uses_no_redirects_and_caps_unsized_stream(self):
        cap = 5 * 1024 * 1024
        remote = SimpleNamespace(
            status_code=200,
            headers={'Content-Type': 'image/png'},
            close=Mock(),
        )
        with (
            smoke.app.test_client() as client,
            patch.object(webapp, 'is_hmac_of', return_value=True),
            patch.object(webapp, 'http_stream', return_value=(
                remote, iter((b'a' * cap, b'x'))
            )) as fetch,
        ):
            response = client.get('/image_proxy?' + urlencode({
                'url': 'https://images.example.org/p.png', 'h': 'synthetic'
            }))
            self.assertEqual(200, response.status_code)
            self.assertEqual(cap, len(response.get_data()))
            self.assertNotIn('Content-Length', response.headers)
            response.close()
            remote.close.assert_called_once()
            self.assertIs(False, fetch.call_args.kwargs['allow_redirects'])

    def test_rejects_malformed_declared_size_before_streaming(self):
        remote = SimpleNamespace(
            status_code=200,
            headers={'Content-Type': 'image/png', 'Content-Length': 'unknown'},
            close=Mock(),
        )
        with (
            smoke.app.test_client() as client,
            patch.object(webapp, 'is_hmac_of', return_value=True),
            patch.object(webapp, 'http_stream', return_value=(remote, iter(()))),
        ):
            response = client.get('/image_proxy?' + urlencode({
                'url': 'https://images.example.org/p.png', 'h': 'synthetic'
            }))
            self.assertEqual(400, response.status_code)
            remote.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
