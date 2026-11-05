"""Opt-in isolated X11 keyboard navigation smoke for GoreeCloud Search WebKitGTK6.

Uses real XTest Tab/Shift+Tab/Enter key events against an Xvfb-only GTK
window, not scripted DOM focus. Does not use external search providers.
Requires system GTK4, WebKitGTK6, X11/XTest and an authorized Linux machine.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import json
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from goreecloud_search.server import SearchServer
from goreecloud_search.store import import_jsonl, initialize


class Keyboard:
    def __init__(self, xid: int):
        self.x11 = ctypes.CDLL(ctypes.util.find_library("X11"))
        self.xtest = ctypes.CDLL(ctypes.util.find_library("Xtst"))
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x11.XSetInputFocus.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong,
        ]
        self.xtest.XTestFakeKeyEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong,
        ]
        self.x11.XFlush.argtypes = [ctypes.c_void_p]
        self.display = self.x11.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("X display unavailable")
        self.x11.XSetInputFocus(self.display, xid, 1, 0)
        self.x11.XFlush(self.display)

    def key(self, symbol: int, shift: bool = False) -> None:
        keycode = self.x11.XKeysymToKeycode(self.display, symbol)
        if not keycode:
            raise RuntimeError("Key not available in X display")
        if shift:
            modifier = self.x11.XKeysymToKeycode(self.display, 0xFFE1)
            self.xtest.XTestFakeKeyEvent(self.display, modifier, 1, 0)
        self.xtest.XTestFakeKeyEvent(self.display, keycode, 1, 0)
        self.xtest.XTestFakeKeyEvent(self.display, keycode, 0, 0)
        if shift:
            self.xtest.XTestFakeKeyEvent(self.display, modifier, 0, 0)
        self.x11.XFlush(self.display)

    def close(self):
        if self.display:
            self.x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            self.x11.XCloseDisplay(self.display)
            self.display = None


def main() -> int:
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        gi.require_version("GdkX11", "4.0")
        from gi.repository import Gio, GLib, Gtk, GdkX11, WebKit
    except (ImportError, ValueError) as exc:
        print("SKIP platform GTK4/WebKitGTK6/GdkX11 unavailable:", type(exc).__name__)
        return 2
    temp = tempfile.TemporaryDirectory(prefix="gc-search-keyboard-")
    path = Path(temp.name) / "index.sqlite3"
    initialize(path)
    data = Path(temp.name) / "sample.jsonl"
    data.write_text(json.dumps({
        "title": "GoreeCloud Keyboard Guide",
        "description": "Private catalog keyboard acceptance",
        "url": "https://example.org/gc-keyboard",
        "source": "curated",
    }), encoding="utf-8")
    import_jsonl(path, data)
    server = SearchServer(("127.0.0.1", 0), path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state = {"focus": [], "reverse": "", "enter": False, "error": ""}
    key = [None]
    source = [0]

    class Smoke(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="com.goreecloud.Search.KeyboardSmoke",
                             flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.step = 0

        def do_activate(self):
            window = Gtk.ApplicationWindow(application=self)
            window.set_title("GoreeCloud Search isolated keyboard smoke")
            window.set_default_size(390, 720)
            self.window = window
            self.view = WebKit.WebView()
            self.view.connect("load-changed", self.on_load)
            window.set_child(self.view)
            window.present()
            self.view.load_uri(f"http://127.0.0.1:{server.server_port}/")
            source[0] = GLib.timeout_add_seconds(15, self.timeout)

        def timeout(self):
            state["error"] = state["error"] or "Keyboard smoke timed out"
            self.quit()
            return GLib.SOURCE_REMOVE

        def on_load(self, view, event):
            if event != WebKit.LoadEvent.FINISHED:
                return
            try:
                surface = self.window.get_surface()
                key[0] = Keyboard(GdkX11.X11Surface.get_xid(surface))
                self.view.grab_focus()
                GLib.timeout_add(350, self.next_tab)
            except Exception as exc:
                state["error"] = str(exc)
                self.quit()

        def eval(self, js, callback):
            self.view.evaluate_javascript(js, -1, None, None, None, callback, None)

        def next_tab(self):
            key[0].key(0xFF09)
            GLib.timeout_add(130, self.capture_focus)
            return GLib.SOURCE_REMOVE

        def capture_focus(self):
            self.eval("""(() => {
                const e=document.activeElement;
                return e ? e.id || (e.classList?.contains('skip') ? 'skip' :
                    e.classList?.contains('brand') ? 'brand' : e.tagName) : 'none';
            })()""", self.on_focus)
            return GLib.SOURCE_REMOVE

        def on_focus(self, view, task, _data):
            try:
                val = view.evaluate_javascript_finish(task).to_string()
                state["focus"].append(val)
                self.step += 1
                if self.step < 7:
                    GLib.timeout_add(90, self.next_tab)
                else:
                    self.finish_focus()
            except Exception as exc:
                state["error"] = str(exc)
                self.quit()

        def finish_focus(self):
            hits = state["focus"]
            must = ("skip", "theme", "query", "submit", "source-select", "share-query")
            if not all(x in hits for x in must):
                state["error"] = f"Keyboard focus missing elements; observed={hits}"
                self.quit()
                return
            # Advance one real Shift+Tab and verify reverse traversal changes focus.
            key[0].key(0xFF09, shift=True)
            GLib.timeout_add(170, self.capture_reverse)

        def capture_reverse(self):
            self.eval("document.activeElement?.id || 'none'", self.on_reverse)
            return GLib.SOURCE_REMOVE

        def on_reverse(self, view, task, _data):
            try:
                state["reverse"] = view.evaluate_javascript_finish(task).to_string()
                if state["reverse"] != "source-select":
                    raise AssertionError("Shift+Tab did not return from consent to source selector")
                # Use focus on input to prepare text (not claiming typed-key verification),
                # then send a real Enter key and assert the local-only response.
                self.eval("""(() => { const q = document.getElementById('query');
                    q.focus(); q.value = 'GoreeCloud'; return q === document.activeElement; })()""",
                    self.after_prepare)
            except Exception as exc:
                state["error"] = str(exc)
                self.quit()

        def after_prepare(self, view, task, _data):
            try:
                if view.evaluate_javascript_finish(task).to_string() != "true":
                    raise AssertionError("Cannot focus search entry")
                self.view.grab_focus()
                key[0].key(0xFF0D)
                GLib.timeout_add(650, self.inspect_result)
            except Exception as exc:
                state["error"] = str(exc)
                self.quit()

        def inspect_result(self):
            self.eval("""JSON.stringify((() => ({
                count: document.querySelectorAll('#result-list article').length,
                status: document.getElementById('status').textContent,
                source: document.getElementById('source-select').value,
                consent: document.getElementById('share-query').checked
            }))())""", self.after_result)
            return GLib.SOURCE_REMOVE

        def after_result(self, view, task, _data):
            try:
                data = json.loads(view.evaluate_javascript_finish(task).to_string())
                if data["count"] != 1 or "1 result found" not in data["status"]:
                    raise AssertionError(f"Real Enter did not submit local query: {data}")
                if data["source"] != "local" or data["consent"]:
                    raise AssertionError("Local privacy default changed")
                state["enter"] = True
            except Exception as exc:
                state["error"] = str(exc)
            finally:
                self.quit()

    try:
        exit_code = Smoke().run([])
    finally:
        if source[0]:
            try:
                GLib.source_remove(source[0])
            except Exception:
                pass
        if key[0]:
            key[0].close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        temp.cleanup()
    if exit_code == 0 and not state["error"] and state["enter"]:
        print("XTEST WEBKIT KEYBOARD PASS:", state["focus"], "reverse=", state["reverse"])
        return 0
    print("XTEST WEBKIT KEYBOARD FAIL:", state, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
