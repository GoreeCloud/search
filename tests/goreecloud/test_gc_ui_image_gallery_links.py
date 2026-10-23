"""Offline gallery link/preference and GC UI consumer contracts.

No provider, external image, or browser network requests are issued.
"""

from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import Environment, select_autoescape
from lxml import html

from scripts.gc_ui_consumer_audit import audit


ROOT = Path(__file__).resolve().parents[2]
GALLERY = ROOT / "searx/templates/simple/result_templates/images.html"
CSS = ROOT / "searx/static/themes/simple/goreecloud-settings-categories.css"
GC_TOKENS = ROOT / "searx/static/themes/simple/gc-ui/css/gc.v1.generated.css"
GC = 'html[data-gc-consumer="goreecloud-search"]'
LEGACY = "html[data-glaze-consumer]"


def render_gallery(new_tab):
    template = Environment(autoescape=select_autoescape(["html"])).from_string(
        GALLERY.read_text(encoding="utf-8")
    )
    document = template.render(
        result={
            "category": "images",
            "title": "Synthetic title",
            "url": "https://example.test/page",
            "img_src": "https://example.test/original.png",
            "thumbnail_src": "https://example.test/thumb.png",
            "parsed_url": SimpleNamespace(netloc="example.test"),
            "formats": [{"url": "https://example.test/other.png", "label": "PNG"}],
            "engines": ["bing images"],
        },
        index=1,
        image_proxify=lambda url: "/image_proxy?fixture=1" if "thumb" in url else url,
        results_on_new_tab=new_tab,
        icon=lambda name: "",
        _=lambda phrase: phrase,
    )
    return html.fromstring(document)


class GCUIImageGalleryLinkTests(unittest.TestCase):
    def test_image_links_honor_new_tab_preference_with_safe_rel(self):
        for new_tab in (False, True):
            with self.subTest(new_tab=new_tab):
                root = render_gallery(new_tab)
                # Detail-panel close/arrow controls are same-document anchors;
                # only external result destinations follow the preference.
                anchors = root.xpath("//article//a[starts-with(@href, 'https://')]")
                self.assertGreaterEqual(len(anchors), 4)
                for anchor in anchors:
                    self.assertEqual("_blank" if new_tab else None, anchor.get("target"))
                    self.assertEqual(
                        "noopener noreferrer" if new_tab else "noreferrer",
                        anchor.get("rel"),
                    )
                # Image elements must never receive link-only rel/target attrs.
                for image in root.xpath("//article//img"):
                    self.assertIsNone(image.get("target"))
                    self.assertIsNone(image.get("rel"))
                self.assertEqual(
                    ["/image_proxy?fixture=1"],
                    root.xpath('//img[contains(@class, "image_thumbnail")]/@src'),
                )

    def test_image_gallery_consumes_supported_gc_ui_semantics(self):
        css = CSS.read_text(encoding="utf-8")
        official = GC_TOKENS.read_text(encoding="utf-8")
        for suffix in (
            "#main_results #results > #urls.goreecloud-image-results {",
            "#urls.goreecloud-image-results > article.result-images {",
            "#urls.goreecloud-image-results .image_thumbnail {",
            "#urls.goreecloud-image-results .title {",
            "#urls.goreecloud-image-results .source {",
            "#urls.goreecloud-image-results article.result-images a:focus-visible {",
        ):
            self.assertIn(GC + " body.results_endpoint " + suffix, css)
            self.assertNotIn(LEGACY + " body.results_endpoint " + suffix, css)
        for token in (
            "--gc-v1-color-outline", "--gc-v1-color-surface-raised",
            "--gc-v1-color-on-surface", "--gc-v1-color-on-surface-muted",
            "--gc-v1-component-focus-width", "--gc-v1-color-focus-ring",
            "--gc-v1-component-focus-offset",
        ):
            self.assertIn(token + ":", official)
            self.assertIn("var(" + token, css)
        self.assertIn("@media (max-width: 410px)", css)
        self.assertIn("@media (forced-colors: active)", css)
        self.assertIn("outline-color: Highlight;", css)

    def test_migration_shrinks_legacy_surface_without_claiming_ui_acceptance(self):
        report = audit(ROOT, ROOT / "docs/goreecloud/gc-ui-legacy-baseline.json")
        self.assertTrue(report["passed"], report["regressions"])
        self.assertLess(report["active_legacy_lines"], 377)
        self.assertFalse(report["full_gc_ui_acceptance"])


if __name__ == "__main__":
    unittest.main()
