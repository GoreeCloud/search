"""Offline Startpage Images fixture: incomplete cards cannot hide valid images."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from searx.engines import startpage


def card(**overrides):
    item = {
        "altClickUrl": "https://example.org/photo-page",
        "rawImageUrl": "https://cdn.example.org/photo.jpg",
        "thumbnailUrl": "/sp/thumb/photo.jpg",
        "title": "<b>Photograph</b>",
        "format": "JPEG",
        "width": 800,
        "height": 600,
        "filesize": "8192",
    }
    item.update(overrides)
    return item


def parse(*items):
    presenter = {
        "render": {"presenter": {"regions": {"mainline": [
            {"display_type": "images-bing", "results": list(items)}
        ]}}}
    }
    body = "React.createElement(UIStartpage.AppSerpImages, " + json.dumps(presenter) + ")"
    resp = SimpleNamespace(
        url="https://www.startpage.com/sp/search", headers={}, text=body
    )
    with patch.object(startpage, "startpage_categ", "images"):
        return startpage.response(resp)


class StartpageImageCardToleranceTests(unittest.TestCase):
    def test_missing_format_does_not_drop_healthy_image_cards(self):
        results = parse(card(format=None), card(title="Another image"))
        self.assertEqual(2, len(results))
        self.assertEqual("", results[0]["img_format"])
        self.assertEqual("Another image", results[1]["title"])

    def test_incomplete_filesize_does_not_abort_gallery(self):
        results = parse(card(filesize="n/a"), card(title="Survivor"))
        self.assertEqual(2, len(results))
        self.assertIsNone(results[0]["filesize"])
        self.assertEqual("Survivor", results[1]["title"])

    def test_missing_title_keeps_visual_image_with_safe_caption(self):
        results = parse(card(title=None), card(title="Next"))
        self.assertEqual(2, len(results))
        self.assertEqual("Image result", results[0]["title"])
        self.assertEqual("Next", results[1]["title"])

    def test_missing_full_image_source_is_skipped_without_hiding_next_card(self):
        results = parse(card(rawImageUrl=None), card(title="Working image"))
        self.assertEqual(["Working image"], [item["title"] for item in results])

    def test_absolute_https_thumbnail_remains_usable(self):
        results = parse(card(thumbnailUrl="https://images.example.org/thumb.jpg"))
        self.assertEqual("https://images.example.org/thumb.jpg", results[0]["thumbnail_src"])

    def test_malformed_thumbnail_scheme_is_not_adopted(self):
        results = parse(card(thumbnailUrl="javascript:alert(1)"))
        self.assertIsNone(results[0]["thumbnail_src"])

    def test_invalid_thumbnail_url_cannot_abort_neighbor_images(self):
        results = parse(card(thumbnailUrl="https://[bad-host/thumb.jpg"), card(title="Next image"))
        self.assertEqual(2, len(results))
        self.assertIsNone(results[0]["thumbnail_src"])
        self.assertEqual("Next image", results[1]["title"])


if __name__ == "__main__":
    unittest.main()
