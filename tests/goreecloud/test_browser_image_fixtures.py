"""Pure, offline tests for the real-Chrome Images fixture boundary."""

from __future__ import annotations

import struct
import unittest
import zlib

from browser_image_fixtures import (IMAGE_FIXTURE_ORIGIN, IMAGE_GALLERY_COUNT,
                                    image_fixture_index, synthetic_image_png)


class BrowserImageFixtureTests(unittest.TestCase):
    def test_only_expected_synthetic_proxy_targets_are_allowed(self):
        for index in range(1, IMAGE_GALLERY_COUNT + 1):
            self.assertEqual(image_fixture_index(f'{IMAGE_FIXTURE_ORIGIN}{index:02d}.png'), index)
        for raw in (
            IMAGE_FIXTURE_ORIGIN + '00.png',
            IMAGE_FIXTURE_ORIGIN + '17.png',
            IMAGE_FIXTURE_ORIGIN + '01.png?tracking=1',
            'http://browser-fixtures.goreecloud.com/images/01.png',
            'https://evil.example.com/images/01.png',
            IMAGE_FIXTURE_ORIGIN + '../01.png',
            '',
        ):
            self.assertIsNone(image_fixture_index(raw))

    def test_every_fixture_has_independently_decodable_rgb_pixels(self):
        pixels = set()
        for index in range(1, IMAGE_GALLERY_COUNT + 1):
            image = synthetic_image_png(index)
            self.assertEqual(image[:8], b'\x89PNG\r\n\x1a\n')
            length = struct.unpack('>I', image[8:12])[0]
            self.assertEqual(length, 13)
            self.assertEqual(image[12:16], b'IHDR')
            self.assertEqual(struct.unpack('>II', image[16:24]), (4, 3))
            self.assertEqual(image[24:29], b'\x08\x02\x00\x00\x00')
            # The first IDAT block follows the fixed-size IHDR chunk.
            self.assertEqual(image[37:41], b'IDAT')
            encoded_length = struct.unpack('>I', image[33:37])[0]
            rgb_rows = zlib.decompress(image[41:41 + encoded_length])
            self.assertEqual(len(rgb_rows), 39)
            self.assertEqual(rgb_rows[0], 0)
            self.assertEqual(rgb_rows[13], 0)
            self.assertEqual(rgb_rows[26], 0)
            pixels.add(rgb_rows)
        self.assertEqual(len(pixels), IMAGE_GALLERY_COUNT)

    def test_no_unbounded_fixture_indices(self):
        for index in (0, -1, IMAGE_GALLERY_COUNT + 1):
            with self.assertRaises(ValueError):
                synthetic_image_png(index)


if __name__ == '__main__':
    unittest.main()
