"""Headless acceptance of the native desktop's data and privacy boundaries.

GTK4 itself must be checked on a real desktop; these tests deliberately have
no PyGObject dependency, make no outbound calls, and use a disposable FTS5 DB.
"""
from __future__ import annotations

import builtins
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from goreecloud_search import native
from goreecloud_search.store import import_jsonl, initialize


class NativeDesktopFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "catalog.sqlite3"
        initialize(self.db)
        source = Path(self.temp.name) / "catalog.jsonl"
        source.write_text(json.dumps({
            "title": "GoreeCloud local handbook",
            "description": "Private first party desktop search",
            "url": "https://example.org/handbook",
            "source": "Local",
        }) + "\n", encoding="utf-8")
        import_jsonl(self.db, source)

    def test_native_local_catalog_without_http_or_provider_egress(self):
        with patch("goreecloud_search.providers.fetch", side_effect=AssertionError("egress forbidden")):
            rows = native.run_local_query(self.db, "private")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "GoreeCloud local handbook")

    def test_empty_and_query_validation(self):
        self.assertEqual(native.run_local_query(self.db, "unknown"), [])
        for query in ("", " " * 2, "a" * 161):
            with self.subTest(query_length=len(query)):
                with self.assertRaises(ValueError):
                    native.run_local_query(self.db, query)

    def test_native_client_import_requires_no_gtk(self):
        # The module's callable model can be imported on CI without GI/GTK.
        self.assertTrue(callable(native.launch))
        self.assertTrue(callable(native.run_local_query))

    def test_missing_gtk_is_reported_cleanly(self):
        real_import = builtins.__import__

        def isolated_import(name, *args, **kwargs):
            if name == "gi":
                raise ImportError("GTK not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=isolated_import):
            with self.assertRaisesRegex(RuntimeError, "GTK4 desktop libraries unavailable"):
                native.launch(self.db)

    def test_native_widgets_have_explicit_accessible_names(self):
        source = Path(native.__file__).read_text(encoding="utf-8")
        self.assertIn('[Gtk.AccessibleProperty.LABEL], ["Search local documents"]', source)
        self.assertIn('[Gtk.AccessibleProperty.LABEL], ["Search results"]', source)

    def test_async_search_preserves_keyboard_focus(self):
        source = Path(native.__file__).read_text(encoding="utf-8")
        self.assertIn("self.entry.set_editable(False)", source)
        self.assertIn("self.entry.set_editable(True)", source)
        self.assertNotIn("self.entry.set_sensitive(False)", source)

    def test_ui_avoids_markup_rendering_and_remote_search(self):
        source = Path(native.__file__).read_text(encoding="utf-8")
        self.assertIn("Gtk.ApplicationWindow", source)
        self.assertIn("Gtk.SearchEntry", source)
        self.assertIn("Gtk.ListBox", source)
        self.assertIn("Gtk.LinkButton", source)
        self.assertIn("set_wrap(True)", source)
        self.assertNotIn("set_markup(", source)
        self.assertNotIn("https://api.search.brave.com", source)
        self.assertNotIn("http.client", source)


if __name__ == "__main__":
    unittest.main()
