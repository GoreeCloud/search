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

## Additional enlarged-text reflow regression — November 4

A second independent check of the same Search preview deliberately increased the **root HTML font size** to **200% and 400%** (CSS text scaling, **not genuine browser/page zoom**) after loading a synthetic one-result page. Chromium and Firefox each tested 320, 390 and 768 CSS-pixel widths in light and dark mode: **24 independent browser/viewport/theme/scale scenarios**.

Before the CSS correction, **12/24 scenarios** scrolled horizontally: all four 320px × 200% and 320px × 400% cases, plus all four 390px × 400% cases. DOM investigation traced it to the non-wrapping mobile masthead, unbroken enlarged hero/intro strings, the minimum-content width of the result grid/card, and non-wrapping result-count/footer text; a small internal search-input scroll was also observed but did **not** require clipping or changing its native input behavior.

The **CSS-only** correction wraps the narrow masthead, gives its brand a shrinkable text container, permits long-word wrapping where necessary, uses a zero-min-width result grid column/card, and allows result-counter, intro and footer text to wrap. It does **not** introduce `overflow-x:hidden` or discard information. Rerunning the identical 24 scenarios gave **24/24 with no document-level overflow**, no off-viewport essential block among the selected heading/input/submit/source/status/result/footer elements, and no browser JS errors. Representative top-of-viewport 320px screenshots at both text scales were inspected. Additional `tests/test_ui_contract.py` source-level guards protect the reflow decisions.

The complete **64-state axe run was repeated after this CSS change**: still **zero confirmed violations**, with **96 accumulated inconclusive color-contrast observations** across overlapping scenarios, not independently adjudicated. This strengthens bounded browser reflow evidence; it **does not** claim user-controlled Chromium/Firefox zoom, OS text scaling, physical-device keyboard/AT/Orca equivalence, all-page visual acceptance, WCAG 1.4.10 certification or ready-to-ship status.
