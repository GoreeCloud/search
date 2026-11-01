"""Regression: approved Git revision must reject unstaged changes."""
import tempfile
import subprocess
import unittest
from pathlib import Path
from native_search.index import SearchIndex
from native_search.repo_corpus import import_approved_repo_docs

class ApprovedCorpusTests(unittest.TestCase):
    def test_import_and_revision_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            docs = root / 'docs/goreecloud'
            docs.mkdir(parents=True)
            p = docs / 'ROADMAP.md'
            p.write_text('# Roadmap\nNative search indexing.\n')
            def git(*args):
                return subprocess.run(['git', '-C', str(root), *args],
                                      check=True, capture_output=True, text=True).stdout.strip()
            git('init', '-q')
            git('add', 'docs')
            git('-c', 'user.name=GoreeCloud', '-c', 'user.email=dev@example.invalid',
                'commit', '-qm', 'fixture')
            rev = git('rev-parse', 'HEAD')
            with SearchIndex(root / 'db.sqlite') as idx:
                got = import_approved_repo_docs(idx, root, revision=rev,
                       approved_paths=['docs/goreecloud/ROADMAP.md'])
                self.assertEqual(1, got['imported'])
                self.assertEqual(1, len(idx.search('native search')))
                p.write_text('# Changed\nUncommitted content.\n')
                with self.assertRaises(ValueError):
                    import_approved_repo_docs(idx, root, revision=rev,
                           approved_paths=['docs/goreecloud/ROADMAP.md'])
                self.assertEqual(1, idx.count())
