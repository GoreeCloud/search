"""Inspect live GTK4 accessibility metadata in an isolated AT-SPI desktop.

Run ONLY with:
  dbus-run-session -- xvfb-run -a env GC_SEARCH_ATSPI_ISOLATED=1 \
    GDK_BACKEND=x11 python3 scripts/smoke_atspi_native.py

Uses a disposable private catalog, launches a NEW native Search process, and
reads the accessibility tree of that process only. Does not drive Orca speech,
inspect a person's normal desktop, enable providers, or save private content.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from goreecloud_search.store import import_jsonl, initialize


def main() -> int:
    if os.environ.get("GC_SEARCH_ATSPI_ISOLATED") != "1" or not os.getenv("DISPLAY"):
        print("Refusing AT-SPI inspection outside explicit isolated display", file=sys.stderr)
        return 2
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
    except (ImportError, ValueError) as exc:
        print("AT-SPI 2.0 unavailable:", type(exc).__name__, file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="goreecloud-atspi-") as directory:
        root = Path(directory)
        db = root / "index.sqlite3"
        initialize(db)
        sample = root / "fixture.jsonl"
        sample.write_text(json.dumps({
            "title": "Accessible local Search",
            "description": "Private synthetic accessibility test data",
            "url": "https://example.org/accessible-search",
            "source": "local",
        }), encoding="utf-8")
        import_jsonl(db, sample)
        environment = os.environ.copy()
        environment["GTK_A11Y"] = "atspi"
        environment["NO_AT_BRIDGE"] = "0"
        app = subprocess.Popen(
            [sys.executable, "-m", "goreecloud_search.native", "--db", str(db)],
            cwd=ROOT, env=environment, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        found = {}
        try:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline and app.poll() is None:
                try:
                    desktops = [Atspi.get_desktop(i) for i in range(Atspi.get_desktop_count())]
                    for desktop in desktops:
                        for i in range(min(desktop.get_child_count(), 50)):
                            candidate = desktop.get_child_at_index(i)
                            if candidate is None:
                                continue
                            name = candidate.get_name() or ""
                            if "GoreeCloud Search" not in name:
                                continue
                            stack = [(candidate, 0)]
                            while stack and len(found) < 60:
                                node, depth = stack.pop()
                                try:
                                    label = node.get_name() or ""
                                    role = node.get_role_name() or ""
                                    if label:
                                        found[label] = role
                                    if depth < 10:
                                        for j in reversed(range(min(node.get_child_count(), 60))):
                                            child = node.get_child_at_index(j)
                                            if child is not None:
                                                stack.append((child, depth + 1))
                                except Exception:
                                    continue
                except Exception:
                    pass
                if "Search local documents" in found and "Search results" in found:
                    break
                time.sleep(.2)
        finally:
            if app.poll() is None:
                app.terminate()
                try:
                    app.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    app.kill()
                    app.wait(timeout=3)
        expected = ("Search local documents", "Search results")
        passed = all(name in found for name in expected)
        print("AT-SPI isolated GTK4 labels:", {name: found.get(name) for name in expected})
        print("AT-SPI NATIVE", "PASS" if passed else "FAIL")
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
