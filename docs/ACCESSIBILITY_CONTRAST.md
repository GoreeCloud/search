# GoreeCloud Search — Targeted text contrast acceptance

**Date:** 2026-11-02  
**Scope:** Original browser Search UI lagoon accent; targeted, source-verified text tokens. **Not** a full WCAG/manual visual certification.

**Authoritative design reference:** GoreeCloud UI `GoreeCloud/gc-ui` `styles/tokens.css` (`main` read at blob `a6c1c45a54eb5e081f0fdbe169faabca5963e887`). The Search interface preserves the approved lagoon brand value and uses the already-defined `--gc-on-brand-container` token for small type appearing on the page canvas.

## Fixed contrast regression

| Content / surface | Before | After | Target |
| --- | --- | --- | --- |
| Small lagoon eyebrow/brand text on light canvas `#ecf0f8` | `#087c8d`: **4.30:1** | Canonical `#07565d`: **7.36:1** | At least 4.5:1 for normal text |
| Small lagoon eyebrow/brand text on dark canvas `#10131e` | Existing dark semantic brand varied | Canonical `#c8fcff`: **16.60:1** | At least 4.5:1 |
| Light source labels on `#f9fafd` | `#087c8d`: **4.70:1** | Kept existing approved brand | At least 4.5:1 |
| Dark source labels on `#1d2231` | `#89e1e9`: **10.57:1** | Kept existing approved brand | At least 4.5:1 |

Ratios computed using WCAG relative-luminance formula over the six-digit CSS color tokens. The base `--gc-brand` token was not arbitrarily altered. The larger hero heading can retain normal lagoon branding, while small text and the masthead brand wordmark use `--gc-on-brand-container` for light-theme contrast.

`tests/test_contrast.py` reads actual Search CSS scopes and computes contrast for both appearances, with four no-skip regression checks. The existing `scripts/smoke_webkit6.py` also exercises the **real** computed page background when toggling light to dark and back under WebKitGTK 6.0 on a 390px isolated Xvfb window. An authorized Linux machine reported `WEBKIT6 SMOKE PASS` after the change; the separately maintained XTest keyboard test also passed with real Tab, Shift+Tab and Enter events.

## Remaining acceptance

Token-level contrast checks are **not** pixel-level audits of every link/button/state, forced colors, focus appearance, font scaling, zoom, display profile or screenshot-rendered content. Manual GC UI pixel comparisons, real Orca screen-reader announcements and broader browser/device testing remain required before Stable/Seal. External providers stay disabled by default; no paid traffic or production deployment was used for these tests.
