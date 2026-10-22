# GoreeCloud Search — GC UI consumer migration ledger

**Authority:** GoreeCloud UI (GC UI), as designated by the current GoreeCloud master instructions and `GoreeCloud/gc-ui` succession policy. **Status:** Migration required; Search is *not* a qualified GC UI consumer. This ledger inventories active legacy behavior without approving its continued expansion.

## Verified Development source inventory (October 22, 2026)

| Consumer boundary | Retired contract still used | Migration disposition |
| --- | --- | --- |
| `searx/templates/simple/base.html` | Bundled `glaze-v1.4.1.css` import, `data-glaze-*` document/surface attributes | Replace actual visual and semantic runtime contract before removing compatibility selectors. |
| `searx/static/themes/simple/goreecloud-search.css` | `html[data-glaze-consumer]` styles and `--glz141-*` semantic variables | Map deliberate Search-specific styles to the official GC UI Foundations API; validate contrast and theme behavior. |
| `searx/static/themes/simple/goreecloud-results.css` | Legacy selector-qualified result layout and feedback styles | Preserve truthful source attribution, incomplete-result notices, keyboard controls, result density and phone reflow during migration. |
| `searx/static/themes/simple/goreecloud-mockup.css` | Legacy selector-qualified owner mockup treatment | Compare actual rendered desktop/phone screenshots against approved owner visual references; do not claim approval based on inherited screenshots. |
| `searx/static/themes/simple/goreecloud-settings-categories.css` | Legacy selector-qualified settings/forms | Preserve native form semantics, POST-only preferences, source selection and assistive-technology navigation. |
| `searx/static/themes/simple/glaze/css/` | 66 historical bundled CSS files, including imported stylesheet chain | Retain only as explicitly inventoried historical compatibility until no active Search route imports them. Never use as a basis for new design. |

The source inventory counts **440 legacy-token-bearing first-party lines in five active files** at the pinned Development baseline. The count is a migration metric, not a measure of visual quality. The baseline is stored at `docs/goreecloud/gc-ui-legacy-baseline.json`.

## Contract and automation

- CI runs `python scripts/gc_ui_consumer_audit.py` and **fails on new legacy consumer files or increased legacy-token-bearing lines**. Legitimate migration can shrink any count without changing the baseline. Changing an allowance needs a separately justified migration review; do not raise the baseline merely to satisfy CI.
- `python scripts/gc_ui_consumer_audit.py --json` shows the complete currently observed debt. `--strict` fails until there are **zero active first-party legacy references**. A strict pass is necessary for retirement, **not sufficient** for GC UI design, accessibility, platform or production qualification.
- This is source-wide static detection of token-bearing lines, not CSS dependency-graph or computed-style analysis. The 66 bundled CSS files are reported separately. Changes with equivalent semantics that avoid these keywords still require human review.
- The existing synthetic browser smoke tests the current legacy rendering for regressions. Its artifact is deliberately named `search-legacy-ui-browser-smoke`. These screenshots are not GC UI conformance evidence by themselves.

## Controlled migration and separate acceptance gates

1. **Pin a real supported GC UI Foundations release.** The upstream scoped `foundations-v1.0.1` release has stable theme/token/contrast helpers and CSS/JSON tokens, but does **not** certify an entire component library or native implementations. Verify an exact package archive, checksum, license, exports and runtime compatibility before adoption. Do not import unqualified alpha workspaces or assume public npm availability.
2. **Map semantics instead of renaming selectors.** Inventory actual CSS cascade/DOM behavior and source-specific layout, implement the corresponding GC UI token/theme contract, remove the retired runtime import, then shrink the five first-party legacy surfaces without blindly replacing names.
3. **Prove Search functionality.** Maintain safe POST navigation, selected-provider continuity, explicit source error and partial-result disclosure, privacy, translation, accessible focus, contrast, reduced-motion, forced-colors, screen-reader announcement and small-device no-overflow behavior.
4. **Verify rendered experience.** Produce fresh authenticated Development screenshots at desktop and phone breakpoints, use approved owner references for comparison, test keyboard/assistive technology and real devices. A source edit or a synthetic screenshot alone is insufficient.
5. **Qualify distinct systems honestly.** GC UI controls presentation. Identity, Policy, Privacy Shield, Wardveil Security, Manager, Everkeep, Mesh and Observability retain their separate authorities and must not be implied by visual decoration. Any native host requires native implementation/verification, not a WebView label.
6. **Release only with runtime evidence.** Keep private Development and retained rollback intact until UI, provider availability, source privacy, access and rollback gates are independently satisfied. Do not equate a successful CI run or merged PR with Stable.

Historical mentions of Glaze in prior test names and records may remain to describe exactly what is still running; these are not current design instructions. In particular, existing `GLAZE-INTEGRATION.md` describes an inherited contract and is superseded for new decisions by this ledger and the upstream GC UI succession policy.
