"""Synthetic Images browser-acceptance data; no network or user content."""

from __future__ import annotations

import re
import struct
import zlib


IMAGE_GALLERY_COUNT = 16  # Exercise the >12 lazy-thumbnail path.
IMAGE_FIXTURE_ORIGIN = 'https://browser-fixtures.goreecloud.com/images/'
_IMAGE_FIXTURE_PATTERN = re.compile(re.escape(IMAGE_FIXTURE_ORIGIN) + r'(\d{2})\.png')


def image_fixture_index(raw: str) -> int | None:
    """Only the sixteen synthetic remote-looking image URLs are eligible."""
    match = _IMAGE_FIXTURE_PATTERN.fullmatch(raw)
    if not match:
        return None
    index = int(match.group(1))
    return index if 1 <= index <= IMAGE_GALLERY_COUNT else None


def synthetic_image_png(index: int) -> bytes:
    """Build valid unique 4x3 RGB PNG bytes locally, without image libraries."""
    if not 1 <= index <= IMAGE_GALLERY_COUNT:
        raise ValueError('synthetic image index outside fixture range')
    color = ((index * 39) % 205 + 35, (index * 71) % 205 + 35, (index * 101) % 205 + 35)
    scanline = b'\x00' + bytes(color) * 4
    pixels = scanline * 3

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack('>I', len(payload)) + kind + payload +
                struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff))

    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 3, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))
