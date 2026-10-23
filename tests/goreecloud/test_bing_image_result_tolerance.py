"""Bing Images must preserve healthy cards when an upstream card is malformed.

Synthetic DOM only; the tests never contact a search provider.
"""

import html
import json
import unittest
from types import SimpleNamespace

from lxml import html as lxml_html

from searx.engines import bing_images


def image_card(*, metadata=None, raw_json=None, title='Caption', link_title=None):
    if raw_json is None:
        raw_json = json.dumps(metadata or {
            'purl': 'https://example.org/page',
            'turl': 'https://cdn.example.org/thumb.jpg',
            'murl': 'https://cdn.example.org/full.jpg',
        })
    title_markup = f'<a title="{html.escape(link_title)}"></a>' if link_title is not None else ''
    return (
        '<li><a class="iusc" m="' + html.escape(raw_json, quote=True) + '"></a>'
        '<div class="infnmpt"><a>' + html.escape(title) + '</a>' + title_markup + '</div>'
        '<div class="imgpt"><div><span>1200x800 · JPG</span></div></div></li>'
    )


def parse(*cards):
    doc = lxml_html.fromstring('<ul class="dgControl_list">' + ''.join(cards) + '</ul>')
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

    def test_non_object_metadata_and_missing_title_are_bounded(self):
        results = parse(image_card(raw_json='[]'), image_card(title=''),
                        image_card(title='Visible'))
        self.assertEqual(['Visible'], [result.title for result in results])

    def test_fallback_caption_from_metadata_when_dom_title_is_absent(self):
        results = parse(image_card(metadata={
            'purl': 'https://example.org/page',
            'turl': 'https://cdn.example.org/thumb.jpg',
            'murl': 'https://cdn.example.org/full.jpg',
            't': 'Metadata caption',
        }, title=''))
        self.assertEqual(['Metadata caption'], [result.title for result in results])


if __name__ == '__main__':
    unittest.main()
