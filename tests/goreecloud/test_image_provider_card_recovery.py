"""Offline Images-card tolerance without bypassing upstream provider controls.

Fixtures represent an already-authorized successful response. No provider,
network, browser automation, API key or upstream index is contacted.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_runtime_smoke as _runtime_settings  # noqa: F401
from searx.engines import brave, duckduckgo_extra as ddg
from searx.exceptions import SearxEngineAPIException, SearxEngineResponseException


PUBLISHER = 'https://publisher.example.org/photos/original'
MEDIA = 'https://cdn.publisher.example.org/image.jpg'
SECOND_PUBLISHER = 'https://publisher.example.org/photos/second'
SECOND_MEDIA = 'https://cdn.publisher.example.org/second.png'


def ddg_image(**overrides):
    card = {
        'url': PUBLISHER,
        'image': MEDIA,
        'thumbnail': 'https://thumbnail.example.org/first.jpg',
        'title': 'Original title',
        'width': 480,
        'height': 320,
        'source': 'Publisher name',
    }
    card.update(overrides)
    return card


def brave_image(**overrides):
    card = {
        'url': PUBLISHER,
        'properties': {'url': MEDIA, 'width': 480, 'height': 320},
        'thumbnail': {'src': 'https://thumbnail.example.org/first.jpg'},
        'title': 'Original title',
        'source': 'Publisher name',
    }
    card.update(overrides)
    return card


def brave_response(items):
    # Mock the deterministic embedded-JSON parsing seam, never HTTP.
    with patch.object(brave, 'brave_category', 'images'), \
            patch.object(brave, 'extract_json_data', return_value={'synthetic': True}), \
            patch.object(brave, '_get_response_data', return_value={'results': items}):
        return brave.response(SimpleNamespace(text='offline-fixture'))


class DuckDuckGoImageRecoveryTests(unittest.TestCase):
    def parse(self, payload):
        with patch.object(ddg, 'ddg_category', 'images'):
            return ddg.response(SimpleNamespace(json=lambda: payload))

    def test_missing_optional_fields_recover_and_preserve_provenance(self):
        items = [
            None,
            ddg_image(),
            {'url': 'javascript:alert(1)', 'image': MEDIA},
            ddg_image(url=SECOND_PUBLISHER, image=SECOND_MEDIA, title=None,
                      thumbnail='https://invalid.example:99999/no.jpg',
                      width=None, height=None, source=None),
            {'url': PUBLISHER, 'image': 'data:image/svg+xml;bad'},
        ]
        results = self.parse({'results': items})
        self.assertEqual(2, len(results))
        self.assertEqual(PUBLISHER, results[0].url)
        self.assertEqual(MEDIA, results[0].img_src)
        self.assertEqual('Publisher name', results[0].source)
        self.assertEqual('480 x 320', results[0].resolution)
        self.assertEqual(SECOND_PUBLISHER, results[1].url)
        self.assertEqual(SECOND_MEDIA, results[1].img_src)
        self.assertEqual(SECOND_MEDIA, results[1].thumbnail_src)
        self.assertEqual('Image result', results[1].title)
        self.assertEqual('', results[1].resolution)
        self.assertEqual('', results[1].source)

    def test_broken_nonempty_response_is_an_error_not_a_false_empty_success(self):
        with self.assertRaisesRegex(SearxEngineAPIException, 'no usable image cards'):
            self.parse({'results': [ddg_image(url='file:///etc/passwd'), None]})

    def test_unexpected_response_envelopes_fail_closed(self):
        for envelope in ({'error': 'denied'}, {'results': None}, {'results': {}}, []):
            with self.subTest(envelope=envelope):
                with self.assertRaises(SearxEngineAPIException):
                    self.parse(envelope)

    def test_confirmed_empty_list_is_empty(self):
        self.assertEqual([], self.parse({'results': []}))

    def test_proxy_rejected_thumbnail_falls_back_to_original(self):
        for thumbnail in ('http://cdn.publisher.example.org/first.jpg',
                          'https://127.0.0.1/private.jpg',
                          'https://localhost/private.jpg'):
            with self.subTest(thumbnail=thumbnail):
                result = self.parse({'results': [ddg_image(thumbnail=thumbnail)]})
                self.assertEqual(MEDIA, result[0].thumbnail_src)

    def test_proxy_rejected_original_does_not_displace_valid_neighbor(self):
        result = self.parse({'results': [ddg_image(image='http://cdn.publisher.example.org/a.jpg'),
                                         ddg_image()]})
        self.assertEqual(1, len(result))
        self.assertEqual(MEDIA, result[0].img_src)


class BraveImageRecoveryTests(unittest.TestCase):
    def test_missing_thumbnail_and_bad_neighbor_do_not_hide_valid_cards(self):
        items = [
            brave_image(),
            brave_image(url='https://user:secret@example.org/a'),
            brave_image(url=SECOND_PUBLISHER, properties={'url': SECOND_MEDIA},
                        thumbnail=None, title=None, source=None),
            brave_image(properties=None),
            'malformed-card',
        ]
        results = brave_response(items)
        self.assertEqual(2, len(results))
        self.assertEqual(PUBLISHER, results[0].url)
        self.assertEqual('Publisher name', results[0].source)
        self.assertEqual('480x320', results[0].resolution)
        self.assertEqual(SECOND_PUBLISHER, results[1].url)
        self.assertEqual(SECOND_MEDIA, results[1].img_src)
        self.assertEqual(SECOND_MEDIA, results[1].thumbnail_src)
        self.assertEqual('Image result', results[1].title)
        self.assertEqual('', results[1].resolution)
        self.assertEqual('', results[1].source)

    def test_nonempty_unusable_response_is_upstream_error(self):
        with self.assertRaisesRegex(SearxEngineResponseException, 'no usable image cards'):
            brave_response([brave_image(properties={'url': 'javascript:blocked'}), None])

    def test_invalid_list_type_is_upstream_error(self):
        with self.assertRaisesRegex(SearxEngineResponseException, 'Unexpected Brave images result list'):
            brave_response({'unexpected': 'denied'})

    def test_confirmed_empty_list_is_empty(self):
        self.assertEqual([], brave_response([]))

    def test_proxy_rejected_thumbnail_falls_back_to_original(self):
        for thumbnail in ('http://cdn.publisher.example.org/first.jpg',
                          'https://127.0.0.1/private.jpg',
                          'https://localhost/private.jpg'):
            with self.subTest(thumbnail=thumbnail):
                result = brave_response([brave_image(thumbnail={'src': thumbnail})])
                self.assertEqual(MEDIA, result[0].thumbnail_src)

    def test_proxy_rejected_original_does_not_displace_valid_neighbor(self):
        result = brave_response([brave_image(properties={'url': 'https://localhost/secret.jpg'}),
                                 brave_image()])
        self.assertEqual(1, len(result))
        self.assertEqual(MEDIA, result[0].img_src)


if __name__ == '__main__':
    unittest.main()
