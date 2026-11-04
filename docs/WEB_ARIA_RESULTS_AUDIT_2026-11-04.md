# GoreeCloud Search — Search Results ARIA Regression Evidence

**Date:** November 4, 2026  
**Scope:** Current original first-party Search **draft PR #2** `web/index.html`, with a local isolated browser mock. **Development only; not a release or WCAG certification.**  
**Baseline PR head:** `c0ba1bac3b3d9ce6e0e3a0b7795e02d99b7fc49b`.  
**Draft review:** https://github.com/GoreeCloud/search/pull/2

## Defect: a name on an unroled div

In the baseline, the live result list was a generic `<div id="result-list">` with `aria-label="Search results"` and `aria-busy="false"`. An `aria-label` on this unnamed generic container is prohibited unless it receives an appropriate supporting role. Its enclosing `<section id="results" aria-labelledby="results-heading">` **already provides an accessible Results region**, so the redundant label is unnecessary.

## Independent browser reproduction

I fetched the exact baseline HTML, JS and CSS from the canonical public Search PR, copied them to a temporary QA directory on an authorized Linux laptop, and served them via an isolated ephemeral `127.0.0.1` **synthetic mock**, with zero real provider connections, user data, credentials, crawler requests or paid usage. Real Playwright Chromium and Firefox each exercised 320, 390, 768 and 1440 CSS-pixel widths; light and dark appearance; and **initial, populated local results, no matches, and synthetic search-error states**.

The installed axe-core was executed against the rendered DOM with WCAG 2A, 2AA and 2.1AA tags. In **64 total scenarios**, baseline axe reported **48 confirmed `aria-prohibited-attr` rule failures** on the same `#result-list` selector in overlapping states. This is **one repeated element-level defect**, not 48 distinct defects. The 16 populated scenarios returned that selector as inconclusive for the same rule.

A minimal source-only correction removes `aria-label` from the generic result-list div, retaining its live `aria-busy` and the already-named parent Results section. Re-running the **same 64 states** produced **zero confirmed automated violations**. The fixture also checked no document-level horizontal overflow, no browser JS exception, non-busy result states after completion, and no non-loopback request in these scenarios.

The post-fix run still contained **96 inconclusive color-contrast observations summed across overlapping browser states**. They were not waived or converted to passes; human perception, dynamic contrast, semantic interpretation, assistive-technology speech, real WebKitGTK/native controls and actual authenticated/loopback SearchServer acceptance remain open.

## Maintained regression

`tests/test_ui_contract.py` now verifies that the outer Results section retains its `aria-labelledby` heading, that the result div retains its `aria-busy` contract, and that generic unroled div markup cannot accidentally reintroduce the prohibited `aria-label`.

No changes were made to query handling, provider availability, external-consent behavior, search-result filtering, privacy safeguards, HTTP routes, native desktop behavior, dependencies, or release status. Browser-script evidence lives in the authorized disposable QA workspace, not in a public user-data archive.

## Remaining acceptance

- Run the browser/contrast and keyboard matrix against the actual local `SearchServer`, including real WebKitGTK and native GTK4 as permitted by the authorized test environment.
- Human AT/Orca announcement walkthroughs, zoom, contrast/incomplete adjudication, focus outlines, device rendering, and visual GC UI parity.
- Qualified review and owner approval before merging greenfield PR #2 or publishing a build.
