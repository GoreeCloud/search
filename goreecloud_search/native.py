"""Native GoreeCloud Search desktop — first-party GTK4 local catalog client.

The GUI is an optional platform integration. Its initial scope is deliberately
local-only: it calls the same private SQLite index directly, with no HTTP
server, remote provider, credentials, or query transmission.
"""
from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from .store import search as local_search, safe_url


def run_local_query(db_path: Path, query: str, limit: int = 12) -> list[dict[str, str]]:
    """Pure GTK-independent boundary, retained for offline tests."""
    return local_search(db_path, query, limit)


def launch(db_path: Path, argv: list[str] | None = None) -> int:
    """Load GTK only on a desktop that explicitly has PyGObject GTK4 installed."""
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio, GLib, Gtk
    except (ImportError, ValueError) as exc:
        raise RuntimeError(
            "GTK4 desktop libraries unavailable. Install PyGObject/Gtk4 via your "
            "operating system package manager; the local Search service remains optional."
        ) from exc

    class SearchDesktop(Gtk.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="com.goreecloud.Search.Development",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )
            self._generation = 0
            self._window = None

        def do_activate(self) -> None:
            if self._window is not None:
                self._window.present()
                return
            window = Gtk.ApplicationWindow(application=self)
            window.set_title("GoreeCloud Search — Local")
            window.set_default_size(940, 680)

            layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            for side in ("top", "bottom", "start", "end"):
                getattr(layout, f"set_margin_{side}")(22)

            brand = Gtk.Label(label="GoreeCloud Search")
            brand.set_xalign(0)
            brand.add_css_class("title-1")
            layout.append(brand)

            description = Gtk.Label(
                label="Search your approved local collection. No search query leaves this device."
            )
            description.set_xalign(0)
            description.set_wrap(True)
            description.add_css_class("dim-label")
            layout.append(description)

            self.entry = Gtk.SearchEntry()
            self.entry.set_placeholder_text("Search local documents")
            self.entry.set_tooltip_text("Search only the private local catalog")
            self.entry.connect("activate", self._search)
            layout.append(self.entry)

            self.status = Gtk.Label(label="Enter a query to search the local catalog.")
            self.status.set_xalign(0)
            self.status.set_wrap(True)
            layout.append(self.status)

            self.results = Gtk.ListBox()
            self.results.set_selection_mode(Gtk.SelectionMode.NONE)
            self.results.add_css_class("boxed-list")
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_vexpand(True)
            scrolled.set_child(self.results)
            layout.append(scrolled)

            footer = Gtk.Label(label="Local-only Development client · No external providers")
            footer.set_xalign(0)
            footer.add_css_class("dim-label")
            layout.append(footer)

            window.set_child(layout)
            self._window = window
            window.present()
            self.entry.grab_focus()

        def _clear(self) -> None:
            child = self.results.get_first_child()
            while child is not None:
                self.results.remove(child)
                child = self.results.get_first_child()

        def _search(self, _entry) -> None:
            query = self.entry.get_text().strip()
            if not query:
                self.status.set_text("Enter a search term.")
                return
            self._generation += 1
            requested = self._generation
            self._clear()
            self.status.set_text("Searching local documents…")
            self.entry.set_sensitive(False)

            def worker() -> None:
                try:
                    rows = run_local_query(db_path, query)
                    error = None
                except (OSError, ValueError, RuntimeError) as exc:
                    # Avoid exposing file paths or private search contents in UI errors.
                    rows, error = [], type(exc).__name__
                GLib.idle_add(self._show_results, requested, rows, error)

            threading.Thread(target=worker, daemon=True, name="gc-native-search").start()

        def _show_results(self, generation: int, rows: list[dict[str, str]],
                          error: str | None) -> bool:
            if generation != self._generation:
                return GLib.SOURCE_REMOVE
            self.entry.set_sensitive(True)
            if error:
                self.status.set_text("The private catalog is unavailable. Initialize it first.")
            elif not rows:
                self.status.set_text("No local results. Try different keywords.")
            else:
                self.status.set_text(f"{len(rows)} local result(s).")
                for record in rows:
                    self._add_result(record)
            return GLib.SOURCE_REMOVE

        def _add_result(self, record: dict[str, str]) -> None:
            try:
                uri = safe_url(record["url"])
            except (KeyError, ValueError):
                return
            item = Gtk.ListBoxRow()
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            for side in ("top", "bottom", "start", "end"):
                getattr(card, f"set_margin_{side}")(12)
            source = Gtk.Label(label=record.get("source", "Local"))
            source.set_xalign(0)
            source.add_css_class("dim-label")
            card.append(source)
            link = Gtk.LinkButton(uri=uri, label=record.get("title", "Result"))
            link.set_halign(Gtk.Align.START)
            card.append(link)
            snippet = Gtk.Label(label=record.get("description", ""))
            snippet.set_xalign(0)
            snippet.set_wrap(True)
            snippet.set_selectable(True)
            card.append(snippet)
            item.set_child(card)
            self.results.append(item)

    app = SearchDesktop()
    return int(app.run(argv or []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="First-party GoreeCloud Search GTK4 local client")
    parser.add_argument("--db", type=Path, default=Path.home() / ".local/state/goreecloud/search.sqlite3")
    args = parser.parse_args(argv)
    try:
        return launch(args.db)
    except RuntimeError as exc:
        print(f"Cannot launch native client: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
