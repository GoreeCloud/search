# GoreeCloud Search — Native GTK4 Development and Acceptance Evidence

**Date:** November 1, 2026  
**Stage:** Experimental Linux desktop client; NOT released or Stable/Seal.  
**Source:** `goreecloud_search/native.py`, `tests/test_native.py`, `scripts/smoke_gtk4.py` in draft [PR #2](https://github.com/GoreeCloud/search/pull/2).

## Native implementation

- Original, optional **GTK4/PyGObject** application. It is not a webview, wrapped website, recovered implementation or source copy from another search engine.
- Uses the approved local SQLite FTS5 index directly; no HTTP service is required. The native client does not invoke Brave, SearXNG or any external provider.
- Provides a native search entry and accessible GTK list structure with source labels, clickable public HTTPS result links, text descriptions, busy/empty/error status, and non-blocking local search.
- Uses operating-system GTK theme controls and first-party GC UI hierarchy principles. Pixel parity, visual design-system acceptance and assistive-tech validation are **not claimed**.
- PyGObject/Gtk4 is optional and loaded only when the user requests the GUI. The basic HTTP app and GitHub CI do not need it.

## Verified development checks

1. Python 3.11 and 3.12 GitHub Actions runs of the greenfield workflow pass the mandatory 37 no-skip offline test suite, including five headless native contracts. Consult the current PR head's workflow, not a previous workflow run.
2. A separate authorized Linux machine with GTK **4.14.5** and Xvfb executed the native client on an isolated virtual display.
3. Using a disposable, explicitly populated local index, the offscreen GUI smoke validated **window = true**, **search entry = true**, **local result link = true**; process exited **0**.
4. The independently rerunnable `scripts/smoke_gtk4.py` passed with the output `GTK4 native window, input, and result: PASS`. This was a local development test, **not** a CI claim for GTK itself.
5. The isolated X server emitted nonfatal software-renderer and GTK focus-out warnings. Investigate these in real desktop visual/accessibility acceptance rather than suppressing them as certification.

## Reproduce on an authorized GTK4 Linux workstation

First create a private local index and import only approved records (see README). Install `python3-gi`, `gir1.2-gtk-4.0` and optionally `xvfb` using the operating system's trusted package manager.

```bash
python3 -m goreecloud_search.native --db /path/to/private.sqlite3
# For isolated offscreen acceptance against a catalog with a GoreeCloud match:
GDK_BACKEND=x11 xvfb-run -a python3 scripts/smoke_gtk4.py \
  --db /path/to/private.sqlite3 --query GoreeCloud
```

This is not a deployment procedure. No real provider connections or authentication are enabled by these commands.

## Remaining acceptance gates

- Actual desktop visual inspection and GC UI typography/spacing/tokens, light/dark and high-contrast themes.
- Keyboard-only flows, focus announcements, screen-reader behavior, reduced-motion support, and selected/empty/error states with actual assistive technology.
- Running on all intended Linux distributions/versions, native desktop launcher/packaging, resource budgets, desktop error recovery, and release signing.
- Any future opt-in external providers in GTK must add explicit and independently tested query-sharing controls. This initial native UI is **local-only by design**.
