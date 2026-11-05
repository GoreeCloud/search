"""Offline, fail-closed import source and strict JSONL acceptance tests."""
from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from goreecloud_search.store import (
    MAX_IMPORT_BYTES, InvalidDocument, import_jsonl, initialize, search,
)


class SafeJSONLImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "catalog.sqlite3"
        initialize(self.db)
        self.source = self.root / "source.jsonl"
        self.source.write_text(json.dumps({
            "title": "Original Handbook",
            "description": "Private approved document",
            "url": "https://example.org/handbook",
            "source": "curated",
        }) + "\n", encoding="utf-8")
        self.assertEqual(import_jsonl(self.db, self.source), 1)

    def assert_original(self):
        self.assertEqual(
            [row["title"] for row in search(self.db, "handbook")],
            ["Original Handbook"],
        )

    def test_zero_byte_import_cannot_erase_existing_catalog(self):
        self.source.write_bytes(b"")
        with self.assertRaisesRegex(InvalidDocument, "no documents"):
            import_jsonl(self.db, self.source)
        self.assert_original()

    def test_whitespace_only_import_cannot_erase_existing_catalog(self):
        self.source.write_bytes(b"\n \t\r\n\n")
        with self.assertRaisesRegex(InvalidDocument, "no documents"):
            import_jsonl(self.db, self.source)
        self.assert_original()

    def test_duplicate_top_level_fields_cannot_change_index(self):
        self.source.write_text(
            '{"title":"Safe","title":"Override","description":"T",'
            '"url":"https://example.org/demo"}\n', encoding="utf-8",
        )
        with self.assertRaisesRegex(InvalidDocument, "line 1"):
            import_jsonl(self.db, self.source)
        self.assert_original()

    def test_duplicate_nested_fields_are_rejected(self):
        self.source.write_text(
            '{"title":"Safe","description":"T","url":"https://example.org/demo",'
            '"extra":{"access":false,"access":true}}\n',
            encoding="utf-8",
        )
        with self.assertRaises(InvalidDocument):
            import_jsonl(self.db, self.source)
        self.assert_original()

    def test_nonstandard_json_numeric_literals_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                self.source.write_text(
                    '{"title":"Safe","description":"T",'
                    '"url":"https://example.org/demo","extra":' + value + '}\n',
                    encoding="utf-8",
                )
                with self.assertRaises(InvalidDocument):
                    import_jsonl(self.db, self.source)
                self.assert_original()

    def test_symlinked_source_cannot_be_imported(self):
        alias = self.root / "alias.jsonl"
        alias.symlink_to(self.source)
        with self.assertRaises(InvalidDocument):
            import_jsonl(self.db, alias)
        self.assert_original()

    def test_import_source_rejects_nonimmediate_symlink_ancestor(self):
        owned = self.root / "owned"
        private = owned / "nested"
        private.mkdir(parents=True, mode=0o700)
        actual = private / "input.jsonl"
        actual.write_bytes(self.source.read_bytes())
        alias = self.root / "alias"
        alias.symlink_to(owned, target_is_directory=True)
        input_path = alias / "nested" / "input.jsonl"
        self.assertFalse(input_path.parent.is_symlink())
        with self.assertRaisesRegex(InvalidDocument, "Symlinked import"):
            import_jsonl(self.db, input_path)
        self.assert_original()

    def test_import_source_rejects_lexical_parent_traversal(self):
        container = self.root / "child"
        container.mkdir(mode=0o700)
        disguised = container / ".." / "source.jsonl"
        with self.assertRaisesRegex(InvalidDocument, "traversal"):
            import_jsonl(self.db, disguised)
        self.assert_original()

    def test_approved_relative_example_path_still_imports(self):
        # The documented CLI path examples/catalog.jsonl is relative.
        example = Path("examples/catalog.jsonl")
        self.assertTrue(example.is_file(), "Run tests from the project checkout")
        self.assertEqual(import_jsonl(self.db, example), 2)
        self.assertTrue(search(self.db, "GoreeCloud"))

    def test_nonregular_fifo_source_is_rejected_without_blocking(self):
        fifo = self.root / "untrusted-pipe"
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(InvalidDocument):
            import_jsonl(self.db, fifo)
        self.assert_original()

    def test_bounded_read_rejects_file_even_if_initial_stat_underreports(self):
        self.source.write_bytes(b" " * (MAX_IMPORT_BYTES + 1))
        real_fstat = os.fstat
        def smaller(fd: int):
            observed = real_fstat(fd)
            return SimpleNamespace(st_mode=observed.st_mode, st_size=1)
        with patch("goreecloud_search.store.os.fstat", side_effect=smaller):
            with self.assertRaisesRegex(InvalidDocument, "size limit"):
                import_jsonl(self.db, self.source)
        self.assert_original()

    def test_invalid_utf8_source_does_not_replace_index(self):
        self.source.write_bytes(b'{"title":"bad"}\xff\n')
        with self.assertRaisesRegex(InvalidDocument, "UTF-8"):
            import_jsonl(self.db, self.source)
        self.assert_original()

    def test_crlf_and_unicode_line_separator_within_json_remain_valid(self):
        payload = {
            "title": "Validated Unicode",
            "description": "One\u2028field on the same JSON line",
            "url": "https://example.org/unicode",
        }
        self.source.write_bytes(
            (json.dumps(payload, ensure_ascii=False) + "\r\n").encode("utf-8")
        )
        self.assertEqual(import_jsonl(self.db, self.source), 1)
        self.assertEqual(search(self.db, "validated")[0]["title"], "Validated Unicode")


if __name__ == "__main__":
    unittest.main()
