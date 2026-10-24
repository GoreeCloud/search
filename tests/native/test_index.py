# SPDX-License-Identifier: AGPL-3.0-or-later
import tempfile
import unittest
from pathlib import Path

from native_search.index import SearchIndex, clean_query


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'index.db'
        self.store = SearchIndex(self.path)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_owned_search_ranking_and_host(self):
        self.store.add(url='https://docs.goreecloud.com/search', title='Search infrastructure',
                       body='A native index for private GoreeCloud search technology')
        self.store.add(url='https://docs.goreecloud.com/notes', title='Random notes', body='Unrelated article')
        hits = self.store.search('native search')
        self.assertEqual(1, len(hits))
        self.assertEqual('docs.goreecloud.com', hits[0].host)
        self.assertGreaterEqual(hits[0].score, 0)
        self.assertNotIn('query', hits[0].__dict__)

    def test_upsert_replaces_old_text_and_fts_entries(self):
        url = 'https://example.org/page'
        self.store.add(url=url, title='Old', body='historic phrase')
        self.store.add(url=url, title='New', body='different topic')
        self.assertEqual(1, self.store.count())
        self.assertEqual([], self.store.search('historic'))
        self.assertEqual('New', self.store.search('different')[0].title)
        self.store.close()
        self.store = SearchIndex(self.path)
        self.assertEqual(1, len(self.store.search('different')))

    def test_deletion_removes_searchable_terms(self):
        url = 'https://example.org/remove-this-page'
        self.store.add(url=url, title='Disallowed document', body='Takedown request')
        self.assertEqual(1, self.store.count())
        self.assertTrue(self.store.remove(url))
        self.assertEqual([], self.store.search('Takedown'))
        self.assertFalse(self.store.remove(url))

    def test_queries_are_escaped_and_bounded(self):
        self.store.add(url='https://example.org/a', title='A', body='python search sample')
        for malicious in ('" OR *', 'NEAR(', 'python" OR "sample', '<script>alert(1)</script>'):
            self.assertIsInstance(self.store.search(malicious), list)
        for bad in ('', 25, 'a' * 257, ' '.join('word' for _ in range(17))):
            with self.assertRaises(ValueError):
                clean_query(bad)
        with self.assertRaises(ValueError):
            self.store.search('python', limit=True)
        with self.assertRaises(ValueError):
            self.store.search('python', limit=10000)

    def test_rejects_url_credentials_or_leaky_query_parameters(self):
        for url in ('http://example.org/a', 'https://user:pass@example.org/',
                    'https://example.org/path?key=secret', 'https://example.org/a#fragment', 'https://127.0.0.1/',
                    'https://host.local/', 'https://localhost/', 'https://localdomain/'):
            with self.assertRaises(ValueError):
                self.store.add(url=url, title='Bad', body='content')

    def test_owned_images_index_without_media_or_provider_fetch(self):
        self.assertEqual(0, self.store.count_images())
        self.store.add_image(
            page_url='https://gallery.example.org/iris',
            media_url='https://cdn.example.org/iris.png',
            title='Purple iris garden', description='A bright spring flower photo',
            rights_evidence='owner-approved/iris-001')
        hit = self.store.search_images('purple garden')[0]
        self.assertEqual('https://gallery.example.org/iris', hit.page_url)
        self.assertEqual('https://cdn.example.org/iris.png', hit.media_url)
        self.assertEqual('owner-approved/iris-001', hit.rights_evidence)
        self.assertGreaterEqual(hit.score, 0)
        self.assertEqual([], self.store.search_images('unrelated'))
        self.assertEqual(1, self.store.count_images())
        self.store.close()
        self.store = SearchIndex(self.path)
        self.assertEqual(1, len(self.store.search_images('flower')))

    def test_images_upsert_atomicity_and_takedown(self):
        page = 'https://gallery.example.org/iris'
        media = 'https://cdn.example.org/iris.png'
        self.store.add_image(page_url=page, media_url=media, title='Old tulip',
                             rights_evidence='owner/001')
        self.store.add_image(page_url=page, media_url=media, title='New violet',
                             rights_evidence='owner/002')
        self.assertEqual(1, self.store.count_images())
        self.assertEqual([], self.store.search_images('tulip'))
        self.assertEqual('owner/002', self.store.search_images('violet')[0].rights_evidence)
        with self.assertRaises(ValueError):
            self.store.add_images([
                (page, 'https://cdn.example.org/good.jpg', 'Blue orchid', '', 'owner/003'),
                (page, 'http://localhost/private.jpg', 'Bad', '', 'owner/004'),
            ])
        self.assertEqual(1, self.store.count_images())
        self.assertEqual([], self.store.search_images('orchid'))
        self.assertTrue(self.store.remove_image(media))
        self.assertEqual(0, self.store.count_images())
        self.assertEqual([], self.store.search_images('violet'))
        self.assertFalse(self.store.remove_image(media))

    def test_owned_image_urls_and_provenance_fail_closed(self):
        good = ('https://gallery.example.org/photo',
                'https://cdn.example.org/photo.png', 'Good image', 'Painted landscape', 'owner/image-1')
        for bad_media in (
            'http://cdn.example.org/photo.jpg',
            'https://user:secret@cdn.example.org/photo.jpg',
            'https://localhost/image.png', 'https://127.0.0.1/image.png',
            'https://192.168.1.30/img.png', 'https://metadata.internal/photo.png',
            'https://images.example/photo.png', 'https://cdn.example.org/image?token=abc',
            'https://cdn.example.org/img#fragment',
            'https://cdn.example.org:8443/img.png', 'javascript:alert(1)',
            'https://cdn.example.org\\@private/image.png',
        ):
            with self.subTest(bad_media=bad_media), self.assertRaises(ValueError):
                self.store.add_images([(*good[:1], bad_media, *good[2:])])
        for bad_source in ('https://localhost/', 'http://gallery.example.org/',
                           'https://gallery.example.org/?token=secret'):
            with self.subTest(bad_source=bad_source), self.assertRaises(ValueError):
                self.store.add_images([(bad_source, *good[1:])])
        for evidence in ('', 'a b', 'secret@mail.example.org', 'ref?api_key=123',
                         'x' * 257, 17):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.store.add_images([(*good[:4], evidence)])
        for malformed in ([], [good] * 101, [(1, 2)], [good, ('broken',)]):
            with self.subTest(batch=repr(malformed)[:80]), self.assertRaises(ValueError):
                self.store.add_images(malformed)
        self.assertEqual(0, self.store.count_images())

    def test_owned_images_query_and_limit_are_bounded(self):
        with self.assertRaises(ValueError):
            self.store.search_images('flower', limit=True)
        with self.assertRaises(ValueError):
            self.store.search_images('flower', limit=21)
        with self.assertRaises(ValueError):
            self.store.search_images('x' * 257)

    def test_sparse_owned_images_return_real_partial_matches_after_exact(self):
        page = 'https://gallery.example.org/image'
        for filename, title, description in (
                ('1.png', 'Blue orchid', 'Botanical garden'),
                ('2.png', 'Orchid blooms', 'Close-up of blue petals'),
                ('3.png', 'Blue sky', 'Spring meadow'),
                ('4.png', 'Tropical orchid', 'Pink petals'),
                ('5.png', 'Red lantern', 'No matching photo')):
            self.store.add_image(page_url=page, media_url='https://cdn.example.org/'+filename,
                                 title=title, description=description,
                                 rights_evidence='operator-reviewed/'+filename)
        cards = self.store.search_images('blue orchid', limit=5)
        self.assertEqual(4, len(cards))
        self.assertEqual({'1.png', '2.png'},
                         {card.media_url.rsplit('/', 1)[-1] for card in cards[:2]})
        self.assertEqual({'3.png', '4.png'},
                         {card.media_url.rsplit('/', 1)[-1] for card in cards[2:]})
        self.assertEqual(2, len(self.store.search_images('blue orchid', limit=2)))
        self.assertEqual([], self.store.search_images('absent'))
        self.assertEqual(cards, self.store.search_images('blue orchid', limit=5))

    def test_partial_images_require_half_of_distinct_query_terms(self):
        page = 'https://gallery.example.org/image'
        for filename, title in (
                ('a.png', 'Purple tropical orchids in rain forest'),
                ('b.png', 'Purple orchids against sky'),
                ('c.png', 'Orchids in a ceramic pot')):
            self.store.add_image(page_url=page, media_url='https://cdn.example.org/'+filename,
                                 title=title, rights_evidence='operator-reviewed/'+filename)
        results = self.store.search_images('purple tropical orchids clouds', limit=20)
        self.assertEqual(['a.png', 'b.png'],
                         [row.media_url.rsplit('/', 1)[-1] for row in results])
        self.assertEqual([], self.store.search_images('clouds'))

    def test_partial_image_match_folds_accents_consistently_with_fts(self):
        self.store.add_image(page_url='https://gallery.example.org/cafe',
                             media_url='https://cdn.example.org/cafe.png',
                             title='Café table', description='Mug beside a window',
                             rights_evidence='operator-reviewed/cafe')
        self.assertEqual(1, len(self.store.search_images('cafe garden', limit=3)))


if __name__ == '__main__':
    unittest.main()
