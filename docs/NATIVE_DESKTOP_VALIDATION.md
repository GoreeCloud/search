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

1. Python 3.11 and 3.12 GitHub Actions run #77 of the greenfield workflow passed the mandatory 49 no-skip offline test suite (37 original + 12 request-budget tests), including five headless native contracts. Consult the current PR head's workflow, not a previous workflow run.
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

## November 2 assistive-technology diagnostic — not accepted

An experimental process-isolated native accessibility test (`scripts/smoke_atspi_native.py`) was executed on the authorized Linux laptop under an ephemeral Xvfb display and `dbus-run-session`. GTK 4.14.5, Orca 46.1 and the AT-SPI registry were present. The test launched the synthetic local-only Search window successfully, but **the expected GTK client was absent from the AT-SPI registry tree**: neither the search-field accessible name nor the results-list label was discovered. The process was deliberately terminated by the test afterward; graphics warnings were nonfatal.

A second isolated attempt explicitly set the temporary accessibility bus's `org.a11y.Status.IsEnabled` property to true. The registry confirmed the value, but the accessible tree was still not found. The failure is **not** a claim that Orca spoke the names, nor proof that the application lacks accessibility on an actual desktop. It may reflect a GTK4/AT-SPI registration or isolated-session integration issue. Root cause remains unconfirmed.

The diagnostic source was restricted to inspecting the newly launched synthetic child process by exact process ID; it does not intentionally read other desktop apps' labels or trees. Next qualify the client under a properly authorized full desktop session with an actual screen reader, inspect the AT-SPI/GTK bridge and its configuration, and record auditable spoken/focus behavior. Do **not** declare assistive-technology acceptance or Stable/Seal until independently verified.

## Remaining acceptance gates

- Actual desktop visual inspection and GC UI typography/spacing/tokens, light/dark and high-contrast themes.
- Keyboard-only flows, focus announcements, screen-reader behavior, reduced-motion support, and selected/empty/error states with actual assistive technology.
- Running on all intended Linux distributions/versions, native desktop launcher/packaging, resource budgets, desktop error recovery, and release signing.
- Any future opt-in external providers in GTK must add explicit and independently tested query-sharing controls. This initial native UI is **local-only by design**.
