"""Shared GoreeCloud Search vector identity and local-only asset contracts."""
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from lxml import html
import test_runtime_smoke as smoke

ROOT = Path(__file__).resolve().parents[2]
SVG_FILE = ROOT / "searx/static/themes/simple/img/favicon.svg"
SVG_NS = "{http://www.w3.org/2000/svg}"


class SearchIdentityTests(unittest.TestCase):
    headers = {"X-Real-IP": "127.0.0.1"}

    def test_canonical_svg_is_safe_and_minimal_at_small_sizes(self):
        raw = SVG_FILE.read_text(encoding="utf-8")
        graphic = ET.fromstring(raw)
        self.assertEqual(SVG_NS + "svg", graphic.tag)
        self.assertEqual("0 0 64 64", graphic.attrib["viewBox"])
        self.assertEqual("GoreeCloud Search", graphic.find(SVG_NS + "title").text)
        self.assertEqual(1, len(graphic.findall(SVG_NS + "rect")))
        self.assertEqual(1, len(graphic.findall(SVG_NS + "circle")))
        self.assertEqual(1, len(graphic.findall(SVG_NS + "path")))
        self.assertNotIn("linearGradient", raw)
        self.assertNotIn("<filter", raw)
        self.assertNotIn("<text", raw)
        self.assertIn("#13BFD4", raw)
        self.assertIn('stroke="#FFFFFF"', raw)
        for forbidden in ("<script", "<image", "javascript:", "https://", "foreignObject"):
            self.assertNotIn(forbidden, raw)

    def test_manifest_icon_rasters_match_expected_sizes(self):
        import struct

        template = (ROOT / "searx/templates/simple/manifest.json").read_text()
        self.assertEqual(3, template.count("?v=search-identity-3"))
        self.assertIn("img/favicon.svg", template)
        for size in (192, 512):
            with self.subTest(size=size):
                path = SVG_FILE.parent / f"{size}.png"
                raw = path.read_bytes()
                self.assertEqual("89504e470d0a1a0a", raw[:8].hex())
                self.assertEqual((size, size), struct.unpack(">II", raw[16:24]))
                self.assertIn(f"img/{size}.png", template)

    def test_home_header_and_favicon_share_one_source(self):
        with smoke.app.test_client() as client:
            page = client.get("/", headers=self.headers)
            self.assertEqual(200, page.status_code)
            root = html.fromstring(page.data)
            hero = root.xpath('//div[contains(@class,"goreecloud-mark-hero")]/img')
            header = root.xpath('//header//span[contains(@class,"goreecloud-mark-small")]/img')
            fav = root.xpath('//link[@rel="icon"]/@href')
            self.assertEqual((1, 1, 1), (len(hero), len(header), len(fav)))
            self.assertEqual(fav[0], hero[0].get("src"))
            self.assertEqual(fav[0], header[0].get("src"))
            self.assertEqual("", hero[0].get("alt"))
            self.assertEqual("", header[0].get("alt"))
            self.assertEqual("true", hero[0].getparent().get("aria-hidden"))
            self.assertEqual("true", header[0].getparent().get("aria-hidden"))
            self.assertIn("search-identity-3", fav[0])
            self.assertEqual("GoreeCloud Search home", root.xpath(
                '//a[contains(@class,"goreecloud-site-brand")]')[0].get("aria-label"))
            asset = client.get(fav[0], headers=self.headers)
            self.assertEqual(200, asset.status_code)
            self.assertIn("svg", asset.content_type)
            self.assertEqual(SVG_FILE.read_bytes(), asset.data)
            asset.close()
            page.close()


if __name__ == "__main__":
    unittest.main()
