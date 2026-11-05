# GoreeCloud Search — Keyboard accessibility smoke evidence

**Date:** 2026-11-02  
**Scope:** Original first-party Search web application, in a private Linux/Xvfb WebKitGTK 6.0 test. **Not** screen-reader or cross-browser certification.

The optional acceptance script `scripts/smoke_webkit_keyboard.py` uses **actual X11 XTest Tab, Shift+Tab and Enter events** (not DOM-programmatic focus for traversal) against the real Search page rendered in WebKitGTK 6.0. It starts a disposable localhost `SearchServer`, imports a single synthetic record into an owner-private SQLite FTS5 index, and leaves external providers disabled.

## Observed result on authorized Linux laptop

`XTEST WEBKIT KEYBOARD PASS: ['skip', 'brand', 'theme', 'query', 'submit', 'source-select', 'share-query'] reverse= source-select`

The tested focus sequence reached the visible-on-focus skip link, home link, theme toggle, search input, search button, provider selection and per-query consent checkbox. A real Shift+Tab key from consent returned to source selection. After the test prepared a synthetic query value, a **real keyboard Enter** event submitted the local form and displayed the expected one-result status. This proves actual keyboard event dispatch and basic tab navigation; the test does **not** claim the query text itself was typed with physical keys.

The test uses only an isolated Xvfb display and a synthetic local catalog. No credentials, user catalog, external endpoints or paid API traffic were accessed. It requires GTK4, WebKitGTK 6.0, GdkX11, system X11/XTest libraries and a trusted local Python 3 runtime; these optional dependencies are **not** imported by the normal Search service.

## Repeat on authorized Linux development workstation

```bash
GDK_BACKEND=x11 xvfb-run -a python3 scripts/smoke_webkit_keyboard.py
```

The script times out and fails closed if the expected focus order or local result is not observed. Xvfb may emit nonfatal rendering warnings; these do not certify graphics, accessibility or production readiness.

## Important pending acceptance

- Actual assistive-technology speech announcements, roles and labels using Orca or other screen readers, on real hardware.
- Shift+Tab through all controls, keyboard open-link behavior, focus visible under light/dark/high-contrast themes, skip-link target activation, disabled provider explanation, interactive browser permissions and system accessibility settings.
- Responsive device matrix beyond the earlier 390px WebKit smoke, macOS/Windows/browser coverage and reviewed GC UI pixel parity.
- Manual WCAG audit and any release-specific accessibility requirements.

This evidence should be classified as an **isolated keyboard smoke**, not complete UI acceptance. Keep PR #2 draft and unmerged.
