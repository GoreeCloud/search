"""Bing Images must preserve healthy cards when an upstream card is malformed.

Synthetic DOM only; the tests never contact a search provider.
"""

import html
import json
import unittest
from types import SimpleNamespace

from lxml import html as lxml_html

from searx.engines import bing_images


def image_card(*, metadata=None, raw_json=None, title='Caption', link_title=None,
               class_name='iusc', caption_class='infnmpt'):
    if raw_json is None:
        raw_json = json.dumps(metadata or {
            'purl': 'https://example.org/page',
            'turl': 'https://cdn.example.org/thumb.jpg',
            'murl': 'https://cdn.example.org/full.jpg',
        })
    title_markup = f'<a title="{html.escape(link_title)}"></a>' if link_title is not None else ''
    return (
        '<li><a class="' + html.escape(class_name, quote=True) + '" m="'
        + html.escape(raw_json, quote=True) + '"></a>'
        '<div class="' + html.escape(caption_class, quote=True) + '"><a>'
        + html.escape(title) + '</a>' + title_markup + '</div>'
        '<div class="imgpt"><div><span>1200x800 · JPG</span></div></div></li>'
    )


def parse(*cards, list_class='dgControl_list'):
    doc = lxml_html.fromstring('<ul class="' + list_class + '">' + ''.join(cards) + '</ul>')
    return bing_images.response(SimpleNamespace(html=lambda: doc))


class BingImageResultToleranceTests(unittest.TestCase):
    def test_bad_json_card_does_not_drop_valid_cards_after_it(self):
        results = parse(image_card(title='First'), image_card(raw_json='{bad'),
                        image_card(title='Third'))
        self.assertEqual(['First', 'Third'], [result.title for result in results])

    def test_missing_metadata_fields_do_not_drop_other_images(self):
        results = parse(image_card(metadata={'purl': 'https://example.org/page'}),
                        image_card(title='Survivor'))
        self.assertEqual(['Survivor'], [result.title for result in results])

    def test_non_object_metadata_and_missing_title_have_safe_fallback(self):
        results = parse(image_card(raw_json='[]'), image_card(title=''),
                        image_card(title='Visible'))
        self.assertEqual(['Image result', 'Visible'], [result.title for result in results])

    def test_fallback_caption_from_metadata_when_dom_title_is_absent(self):
        results = parse(image_card(metadata={
            'purl': 'https://example.org/page',
            'turl': 'https://cdn.example.org/thumb.jpg',
            'murl': 'https://cdn.example.org/full.jpg',
            't': 'Metadata caption',
        }, title=''))
        self.assertEqual(['Metadata caption'], [result.title for result in results])

    def test_missing_thumbnail_keeps_original_and_publisher_url(self):
        source = {
            'purl': 'https://publisher.example.org/gallery',
            'murl': 'https://cdn.example.org/full.jpg',
            't': 'Full size photograph',
        }
        results = parse(image_card(metadata=source, title=''))
        self.assertEqual(1, len(results))
        self.assertEqual('https://publisher.example.org/gallery', results[0].url)
        self.assertEqual(source['murl'], results[0].img_src)
        self.assertEqual(source['murl'], results[0].thumbnail_src)

    def test_unusable_thumbnail_does_not_discard_valid_image(self):
        metadata = {
            'purl': 'https://example.org/photo',
            'murl': 'https://cdn.example.org/full.jpg',
            'turl': 'javascript:alert(1)',
        }
        results = parse(image_card(metadata=metadata), image_card(title='Next'))
        self.assertEqual(['Caption', 'Next'], [item.title for item in results])
        self.assertEqual(metadata['murl'], results[0].thumbnail_src)

    def test_additional_class_tokens_and_container_variation_keep_images(self):
        results = parse(
            image_card(class_name='lazy iusc imgpt-card', caption_class='infnmpt compact',
                       title='An image'),
            list_class='image_grid',
        )
        self.assertEqual(['An image'], [item.title for item in results])

    def test_missing_or_malformed_required_source_urls_are_excluded(self):
        results = parse(
            image_card(metadata={'purl': 'https://example.org/page',
                                 'turl': 'https://cdn.example.org/thumb.jpg'}),
            image_card(metadata={'purl': 'https://example.org/page',
                                 'murl': 'file:///etc/passwd'}),
            image_card(metadata={'purl': 'https://[invalid/host',
                                 'murl': 'https://cdn.example.org/full.jpg'}),
            image_card(metadata={'purl': 'https://example.org/page',
                                 'murl': 'https://cdn.example.org:invalid/full.jpg'}),
            image_card(title='Healthy'),
        )
        self.assertEqual(['Healthy'], [item.title for item in results])


if __name__ == '__main__':
    unittest.main()
