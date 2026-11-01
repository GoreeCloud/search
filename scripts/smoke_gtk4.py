"""Isolated GTK4 smoke test for the optional GoreeCloud Search native client.

Run with 'xvfb-run -a python3 scripts/smoke_gtk4.py --db ...' on an
authorized Linux workstation with PyGObject/GTK4 installed. Never launches
a browser, queries a remote search provider, or modifies the index.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from goreecloud_search.native import launch, run_local_query


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GTK4 Search offscreen acceptance smoke")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--query", default="GoreeCloud")
    args = parser.parse_args(argv)
    if not run_local_query(args.db, args.query):
        parser.error("Test catalog must contain a local result for --query")

    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, GLib, Gtk

    checks = {"window": False, "entry": False, "local_result": False}
    state = {"ticks": 0, "searched": False}

    def descendants(widget):
        yield widget
        child = widget.get_first_child()
        while child is not None:
            yield from descendants(child)
            child = child.get_next_sibling()

    def inspect() -> bool:
        state["ticks"] += 1
        app = Gio.Application.get_default()
        window = app.get_active_window() if app is not None else None
        if window is not None:
            checks["window"] = window.get_title().startswith("GoreeCloud Search")
            widgets = list(descendants(window))
            entries = [widget for widget in widgets if isinstance(widget, Gtk.SearchEntry)]
            checks["entry"] = bool(entries)
            if entries and not state["searched"]:
                state["searched"] = True
                entries[0].set_text(args.query)
                entries[0].emit("activate")
            checks["local_result"] = any(
                isinstance(widget, Gtk.LinkButton) for widget in widgets
            )
        if checks["local_result"] or state["ticks"] >= 40:
            print("GTK4 isolated smoke:", checks, flush=True)
            if app is not None:
                app.quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    GLib.timeout_add(150, inspect)
    code = launch(args.db)
    if code or not all(checks.values()):
        return 1
    print("GTK4 native window, input, and result: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
