# SPDX-License-Identifier: AGPL-3.0-or-later
"""Operator-only Images metadata import never fetches a remote source."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from native_search.__main__ import load_approved_image_manifest, main
from native_search.index import SearchIndex


def manifest(*, media='https://cdn.example.org/orchid.png', title='Blue orchid'):
    return {'schema_version': 1, 'images': [{
        'page_url': 'https://gallery.example.org/orchid',
        'media_url': media,
        'title': title,
        'description': 'Botanical photo with colored orchid petals',
        'rights_evidence': 'owner-reviewed/orchid-1',
    }]}


class OperatorImageImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.db = self.root / 'owned.sqlite'
        self.source = self.root / 'approved-images.json'

    def write(self, payload):
        self.source.write_text(json.dumps(payload), encoding='utf-8')

    def test_cli_import_only_approved_local_metadata_and_is_repeatable(self):
        self.write(manifest())
        with patch('sys.argv', ['native_search', 'import-images-json',
                                '--db', str(self.db), '--input', str(self.source)]):
            with redirect_stdout(StringIO()) as output:
                main()
        self.assertEqual({'images_imported': 1, 'owned_images': 1}, json.loads(output.getvalue()))
        with SearchIndex(self.db) as index:
            self.assertEqual(1, len(index.search_images('orchid')))

        self.write(manifest(title='Pink orchid'))
        with patch('sys.argv', ['native_search', 'import-images-json',
                                '--db', str(self.db), '--input', str(self.source)]):
            with redirect_stdout(StringIO()):
                main()
        with SearchIndex(self.db) as index:
            self.assertEqual(1, index.count_images())
            self.assertEqual('Pink orchid', index.search_images('Pink orchid')[0].title)
            self.assertEqual([], index.search_images('Blue'))

    def test_rejects_duplicate_fields_and_bad_manifest_shape(self):
        bad = [
            b'{"schema_version":1,"schema_version":1,"images":[]}',
            b'{"schema_version":1,"images":[],"unknown":true}',
            b'{"schema_version":true,"images":[]}',
            b'{"schema_version":1,"images":false}',
            b'{"schema_version":1,"images":[{"media_url":"a","media_url":"b"}]}',
            b'\xff',
            json.dumps(manifest()).encode('utf-16'),
            json.dumps({'schema_version': 1, 'images': manifest()['images'] * 101}).encode(),
            json.dumps({'schema_version': 1, 'images': [manifest()['images'][0],
                                                        manifest()['images'][0]]}).encode(),
        ]
        for value in bad:
            with self.subTest(payload=value[:45]):
                self.source.write_bytes(value)
                with self.assertRaises(ValueError):
                    load_approved_image_manifest(self.source)

    def test_invalid_image_cannot_partially_commit_other_manifest_records(self):
        good = manifest()['images'][0]
        bad = dict(good, media_url='https://127.0.0.1/private.png')
        self.write({'schema_version': 1, 'images': [good, bad]})
        with patch('sys.argv', ['native_search', 'import-images-json',
                                '--db', str(self.db), '--input', str(self.source)]):
            with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as caught:
                main()
        self.assertEqual(2, caught.exception.code)
        with SearchIndex(self.db) as index:
            self.assertEqual(0, index.count_images())

    def test_path_and_size_bounds(self):
        self.write(manifest())
        relative = self.source.name
        with self.assertRaises(ValueError):
            load_approved_image_manifest(relative)
        target = self.root / 'symlink.json'
        target.symlink_to(self.source)
        with self.assertRaises(ValueError):
            load_approved_image_manifest(target)
        self.source.write_bytes(b'x' * 262145)
        with self.assertRaises(ValueError):
            load_approved_image_manifest(self.source)

    def test_operator_can_immediately_remove_approved_image_through_cli(self):
        self.write(manifest())
        with patch('sys.argv', ['native_search', 'import-images-json',
                                '--db', str(self.db), '--input', str(self.source)]):
            with redirect_stdout(StringIO()):
                main()
        target = manifest()['images'][0]['media_url']
        with patch('sys.argv', ['native_search', 'remove-image', '--db', str(self.db),
                                '--media-url', target]):
            with redirect_stdout(StringIO()) as output:
                main()
        self.assertEqual({'removed': True, 'owned_images': 0}, json.loads(output.getvalue()))
        self.assertNotIn(target, output.getvalue())
        with SearchIndex(self.db) as index:
            self.assertEqual([], index.search_images('orchid'))
        with patch('sys.argv', ['native_search', 'remove-image', '--db', str(self.db),
                                '--media-url', target]):
            with redirect_stdout(StringIO()) as output:
                main()
        self.assertEqual({'removed': False, 'owned_images': 0}, json.loads(output.getvalue()))

    def test_missing_or_symlink_takedown_database_fails_without_creating_index(self):
        self.assertFalse(self.db.exists())
        target = manifest()['images'][0]['media_url']
        with patch('sys.argv', ['native_search', 'remove-image', '--db', str(self.db),
                                '--media-url', target]):
            with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as caught:
                main()
        self.assertEqual(2, caught.exception.code)
        self.assertFalse(self.db.exists())

        with SearchIndex(self.db):
            pass
        symlink = self.root / 'link.db'
        symlink.symlink_to(self.db)
        with patch('sys.argv', ['native_search', 'remove-image', '--db', str(symlink),
                                '--media-url', target]):
            with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as caught:
                main()
        self.assertEqual(2, caught.exception.code)

    def test_takedown_never_adds_search_tables_to_an_unrelated_sqlite_file(self):
        unrelated = self.root / 'unrelated.sqlite'
        with sqlite3.connect(unrelated) as database:
            database.execute('CREATE TABLE unrelated(value TEXT)')
        with patch('sys.argv', ['native_search', 'remove-image', '--db', str(unrelated),
                                '--media-url', manifest()['images'][0]['media_url']]):
            with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as caught:
                main()
        self.assertEqual(2, caught.exception.code)
        with sqlite3.connect(unrelated) as database:
            self.assertEqual(['unrelated'], [row[0] for row in database.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")])


if __name__ == '__main__':
    unittest.main()
