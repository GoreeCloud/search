# GoreeCloud Search — Real Browser Validation (WebKitGTK 6.0)

**Date:** November 1, 2026  
**Stage:** Independent Development acceptance evidence; not full accessibility, production or release certification.  
**Draft review:** https://github.com/GoreeCloud/search/pull/2

## What ran

The actual first-party Search repository was pulled to a temporary checkout on an authorized Linux laptop with GTK4 and WebKitGTK 6.0 available. The repeatable test is `scripts/smoke_webkit6.py`, executed under an isolated Xvfb display; it does **not** open a window on the user's desktop. It starts the actual `SearchServer` on an ephemeral 127.0.0.1 port and imports one synthetic, curated record into a disposable private SQLite FTS5 index.

The WebKit WebView loads the actual Search page, JS and CSS over loopback, with **no provider credentials, provider enablement, production server, paid queries or external services**.

## Observed results

The WebKit smoke completed with exit code **0** and reported:

`WEBKIT6 SMOKE PASS: controls, local privacy, mobile width, results, live status`

- Search input and provider select exposed associated labels; a submit button was present.
- Source selection was local-only by default, both external options disabled, query-sharing checkbox unchecked.
- Status exposed role=status and aria-atomic=true; results region initially exposed aria-busy=false.
- At a 390 px window width the document did not exceed the viewport by more than a 3 px tolerance.
- A local query completed against a real SQLite index. One valid HTTPS result link rendered; the result count was 1 and the live-status text announced 1 result found.
- After completion, the list was no longer marked busy; provider selection and query consent remained reset to the local-only default.
- The local WebKit/GDK environment emitted an isolated, nonfatal software-rendering warning. This is not evidence of desktop GPU compatibility or production graphics quality.

The original browser source also passed GitHub's Python/JS integration checks. Refer to the latest PR head and GitHub Actions run before claiming a CI state.

## Reproduction

On an authorized Linux workstation with Python 3, PyGObject, Gtk4, WebKitGTK 6.0, and Xvfb supplied by trusted OS packages, run from the exact GoreeCloud Search checkout:

```bash
GDK_BACKEND=x11 xvfb-run -a python3 scripts/smoke_webkit6.py
```

The script provisions and removes its own private temporary catalog and loopback HTTP listener. No environment variables enabling external providers are required; the test explicitly expects default-off provider availability.

## Not yet accepted

This is a real WebKit browser smoke, **not** manual visual inspection or real screen-reader testing. Remaining checks include keyboard-only Tab/Shift-Tab traversal, high contrast/reduced motion, dark appearance screenshots, mobile touch interaction, Firefox/Chromium/WebKit platform coverage, assistive-technology announcements, Web Content Accessibility Guidelines audit, desktop packaging, backup/rollback and release verification.

SearXNG and Brave remain optional integrations, not native source dependencies; their real API, privacy and billing acceptance remains pending. Historical recovery source is excluded.
