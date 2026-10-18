"""Read-only native index can serve results without writing or network egress."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from native_search.index import SearchIndex
from native_search.readonly import read_native_results

class NativeReadOnlyTests(unittest.TestCase):
    def test_result_and_unchanged_index(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'docs.sqlite'
            with SearchIndex(path) as index:
                index.add(url='https://github.com/GoreeCloud/search/blob/'+'a'*40+
                          '/docs/goreecloud/ROADMAP.md',
                          title='Search roadmap',body='Approved GoreeCloud native search.')
            results=read_native_results(path,'native search')
            self.assertEqual(1,len(results))
            self.assertIn('ROADMAP.md',results[0].url)
            with SearchIndex(path) as index:
                self.assertEqual(1,index.count())

    def test_invalid_query_missing_index_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'absent.sqlite'
            with self.assertRaises(ValueError):
                read_native_results(target,'query')
            with self.assertRaises(ValueError):
                read_native_results('relative.sqlite','query')
            with SearchIndex(target) as index:
                index.add(url='https://example.org/a',title='Test',body='Test document')
            link=Path(temp)/'link.sqlite'
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                read_native_results(link,'document')
            with self.assertRaises(ValueError):
                read_native_results(target,'')
            with self.assertRaises(ValueError):
                read_native_results(target,'document',limit=21)
