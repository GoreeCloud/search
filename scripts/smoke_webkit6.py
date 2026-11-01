"""WebKitGTK 6.0 acceptance smoke for the real loopback Search web interface.

Optional, manual Linux test using Gtk4/WebKit6 and Xvfb. Runs the actual
SearchServer with a disposable local FTS5 catalog; never enables or calls
Brave, SearXNG, or other external resources.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from goreecloud_search.server import SearchServer
from goreecloud_search.store import import_jsonl, initialize


def main() -> int:
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        from gi.repository import Gio, GLib, Gtk, WebKit
    except (ImportError, ValueError) as exc:
        print("WebKitGTK 6.0 and GTK4 required:", type(exc).__name__, file=sys.stderr)
        return 2

    temp = tempfile.TemporaryDirectory(prefix="goreecloud-search-web-smoke-")
    db_path = Path(temp.name) / "catalog.sqlite3"
    initialize(db_path)
    jsonl = Path(temp.name) / "catalog.jsonl"
    jsonl.write_text(json.dumps({
        "title": "GoreeCloud Accessibility Guide",
        "description": "Accessible original search interface",
        "url": "https://example.org/goreecloud",
        "source": "Local",
    }) + "\n", encoding="utf-8")
    import_jsonl(db_path, jsonl)
    server = SearchServer(("127.0.0.1", 0), db_path)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    state = {"complete": False, "passed": False, "error": ""}
    timeout_id = [0]

    class WebSmoke(Gtk.Application):
        def __init__(self):
            super().__init__(
                application_id="com.goreecloud.Search.WebSmoke",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )

        def do_activate(self):
            window = Gtk.ApplicationWindow(application=self)
            window.set_default_size(390, 720)
            window.set_title("GoreeCloud Search isolated WebKit smoke")
            self.view = WebKit.WebView()
            self.view.connect("load-changed", self.on_load)
            window.set_child(self.view)
            window.present()
            self.view.load_uri(f"http://127.0.0.1:{server.server_port}/")
            timeout_id[0] = GLib.timeout_add_seconds(12, self.on_timeout)

        def on_timeout(self):
            if not state["complete"]:
                state["error"] = "Timed out waiting for Search UI"
                self.quit()
            return GLib.SOURCE_REMOVE

        def on_load(self, view, event):
            if event != WebKit.LoadEvent.FINISHED or state["complete"]:
                return
            self.eval_script("""
                const field = document.getElementById('query');
                const provider = document.getElementById('source-select');
                const consent = document.getElementById('share-query');
                const status = document.getElementById('status');
                const list = document.getElementById('result-list');
                const checks = {
                    accessibleLabel: field.labels.length > 0,
                    sourceLabel: provider.labels.length > 0,
                    defaultLocal: provider.value === 'local',
                    remoteDisabled: [...provider.options].filter(x => x.value !== 'local').every(x => x.disabled),
                    consentUnchecked: !consent.checked,
                    liveStatus: status.getAttribute('role') === 'status' && status.getAttribute('aria-atomic') === 'true',
                    busyDefault: list.getAttribute('aria-busy') === 'false',
                    mobileWidth: document.documentElement.scrollWidth <= window.innerWidth + 3,
                    searchButton: document.getElementById('submit')?.type === 'submit',
                };
                field.value = 'GoreeCloud';
                document.getElementById('search-form').requestSubmit();
                JSON.stringify(checks);
            """, self.on_precheck)

        def eval_script(self, script, callback):
            self.view.evaluate_javascript(script, -1, None, None, None, callback, None)

        def on_precheck(self, view, task, _data):
            try:
                result = json.loads(view.evaluate_javascript_finish(task).to_string())
                if not all(result.values()):
                    raise AssertionError("Initial UI contract failed: " + str(result))
            except (Exception,) as exc:
                state["error"] = "UI setup: " + str(exc)
                self.quit()
                return
            GLib.timeout_add(300, self.inspect_results)

        def inspect_results(self):
            self.eval_script("""
                JSON.stringify({
                    results: document.querySelectorAll('#result-list article').length,
                    link: document.querySelector('#result-list a')?.getAttribute('href'),
                    announced: document.getElementById('status').textContent,
                    busy: document.getElementById('result-list').getAttribute('aria-busy'),
                    count: document.getElementById('counter').textContent,
                    consent: document.getElementById('share-query').checked,
                    source: document.getElementById('source-select').value
                });
            """, self.on_result)
            return GLib.SOURCE_REMOVE

        def on_result(self, view, task, _data):
            try:
                data = json.loads(view.evaluate_javascript_finish(task).to_string())
                assert data["results"] == 1, data
                assert data["link"] == "https://example.org/goreecloud", data
                assert "1 result found" in data["announced"], data
                assert data["busy"] == "false", data
                assert data["count"] == "1 result", data
                assert data["consent"] is False and data["source"] == "local", data
                state["passed"] = True
            except Exception as exc:
                state["error"] = "Search results: " + str(exc)
            finally:
                state["complete"] = True
                self.quit()

    try:
        result = WebSmoke().run([])
    finally:
        if timeout_id[0]:
            try:
                GLib.source_remove(timeout_id[0])
            except Exception:
                pass
        server.shutdown()
        server.server_close()
        worker.join(timeout=4)
        temp.cleanup()
    if state["passed"] and result == 0:
        print("WEBKIT6 SMOKE PASS: controls, local privacy, mobile width, results, live status")
        return 0
    print("WEBKIT6 SMOKE FAIL:", state["error"] or f"app result {result}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
