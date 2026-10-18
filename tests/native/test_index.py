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


if __name__ == '__main__':
    unittest.main()
