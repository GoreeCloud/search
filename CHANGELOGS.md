# GoreeCloud Search — Changelogs

**Record type:** Authoritative repository changelog index and current change history  
**Repository:** `GoreeCloud/search`  
**Lifecycle:** Development / nonconformant  
**Migration state:** Authoritative repository record on protected `main`; legacy Drive feature/changelog sources retired and independently verified absent on September 22, 2026.  
**Governance baseline:** `main` at `db15ea4c6e7e29c395204a94cad07d886f9242ff`, merged by PR #30 on September 22, 2026.  
**Current accepted runtime-bearing main:** `66ff984b8dd79624a739ab6117c42a572dc44475`, merged by PR #34 on September 22, 2026.  
**Governing standard:** Standard — Repository Feature Tracking and Changelog Governance v1.0, effective September 22, 2026.

## Authority and interpretation

This file is the repository-local changelog authority for current and future GoreeCloud Search changes. Historical Search chronology formerly stored in Google Drive is preserved under `docs/changelog-history/` as normalized migrated provenance.

Historical entries describe the state, repositories, candidates, deployments, release labels, and evidence that existed at their own dates. They do **not** override current authoritative `main`, current lifecycle, or current architecture. Earlier maintained-fork and prior native-line Production/RC/Stable language must therefore be read as exact-revision historical evidence rather than a claim about the current `0.1.0.dev14` native line.

Draft/unmerged pull requests are not accepted changes. Historical Draft PR #29 remains unmerged provenance; equivalent query-control hardening was independently accepted through PR #34.

## Historical archive migrated from Google Drive

Retired Drive source: `Change Log — Search.docx`, file ID `1uEAtCFrxl8D3HnVxzRInMe92lRAiJKBv`.

The complete meaningful chronology is normalized into eight repository archive files so all 77 dated Drive entries remain represented without making this root index unwieldy:

- [`docs/changelog-history/legacy-drive-history-part-01.md`](docs/changelog-history/legacy-drive-history-part-01.md) — entries 1–10
- [`docs/changelog-history/legacy-drive-history-part-02.md`](docs/changelog-history/legacy-drive-history-part-02.md) — entries 11–20
- [`docs/changelog-history/legacy-drive-history-part-03.md`](docs/changelog-history/legacy-drive-history-part-03.md) — entries 21–30
- [`docs/changelog-history/legacy-drive-history-part-04.md`](docs/changelog-history/legacy-drive-history-part-04.md) — entries 31–40
- [`docs/changelog-history/legacy-drive-history-part-05.md`](docs/changelog-history/legacy-drive-history-part-05.md) — entries 41–50
- [`docs/changelog-history/legacy-drive-history-part-06.md`](docs/changelog-history/legacy-drive-history-part-06.md) — entries 51–60
- [`docs/changelog-history/legacy-drive-history-part-07.md`](docs/changelog-history/legacy-drive-history-part-07.md) — entries 61–70
- [`docs/changelog-history/legacy-drive-history-part-08.md`](docs/changelog-history/legacy-drive-history-part-08.md) — entries 71–77

Those archives preserve the meaningful historical chronology of the retired Drive changelog, including maintained-fork development, deployment/release evidence, native rebuild work, Sync/provider/ranking work, platform and Glaze checkpoints, and later stabilization. They are historical provenance, not a shadow current-state authority.

## Current native-line changelog

### September 23, 2026 — Bounded local snippet-generation source foundation

- Added a local-only, query-aware snippet generator for already-authorized plain text.
- Capped source processing at 32,768 Unicode characters and output at 280 characters, with normalized-window offsets and source-truncation evidence.
- Removed C0/C1 and bidirectional formatting controls before snippet presentation.
- Added regression coverage for query-focused selection, leading-sentence fallback, bounds, sanitization, empty input, and invalid limits.
- This source foundation does not fetch content, add a provider, expose a user-facing Search UI, or establish production/runtime acceptance.

### September 22, 2026 — Repository migration accepted and legacy Drive sources retired

- PR #30, **Migrate Search feature tracking and changelog governance**, merged to protected `main` as `db15ea4c6e7e29c395204a94cad07d886f9242ff`.
- Exact-head CI run #80 / `35731880345` passed on migration candidate `f97aee9bbe985fe262847769f26c318ea7a37a9c`, including Python 3.11 and 3.12.
- Exact-head Platform Contract run #22 / `35731881274` passed on the same candidate.
- After merge, exact-main CI run #81 / `35732002017` passed and Platform Contract run #23 / `35732002972` passed on `db15ea4c6e7e29c395204a94cad07d886f9242ff`.
- Authoritative `main` readback confirmed `IMPLEMENTED-FEATURES.md`, `PLANNED-FEATURES.md`, `CHANGELOGS.md`, and the migrated historical archive are present.
- Authoritative `main` readback confirmed retired root `FEATURE-ROADMAP.md` and singular `CHANGELOG.md` are absent.
- After those deletion gates passed, Drive `Change Log — Search.docx` (`1uEAtCFrxl8D3HnVxzRInMe92lRAiJKBv`) and `goreecloud-search-planned-features-and-capabilities.md` (`1Ja7M0-aWvhg9Zis6WIqeqirD1wTGAl4w`) were permanently deleted.
- Independent post-deletion Drive reads returned `404 / not found` for both retired file IDs.
- Search remains **Development / nonconformant**. This migration and retirement do not add live authority transports, an approved external provider, deployment, Production Acceptance, Release Candidate, or Stable qualification.
- PR #29 remains a separate Draft security candidate and is not included in accepted implementation state.

### September 22, 2026 — Repository feature/changelog governance migration candidate

This entry records the candidate state that preceded the accepted migration above.

- Added root `IMPLEMENTED-FEATURES.md`, `PLANNED-FEATURES.md`, and `CHANGELOGS.md` under the repository-native governance standard.
- Migrated all 77 dated entries from the legacy Drive changelog into eight repository history archives.
- Reconciled former root `FEATURE-ROADMAP.md` and the broader Drive planned-capabilities record into implemented/open feature inventories.
- Retired root `FEATURE-ROADMAP.md` from the migration branch after its material obligations were dispositioned.
- Migrated the content of the former root singular `CHANGELOG.md` into this authoritative changelog and retired the singular file to prevent split changelog authority.
- Reconciled README and repository notes to the new records/current baseline.
- Added a focused repository-governance test to require the three root records and reject the two retired root filenames.
- No runtime source, deployment, provider, authority-service, lifecycle, Production, Release Candidate, or Stable state was changed by this migration candidate.

### September 21, 2026 — PR #28: fail closed readiness until authority transports are accepted

- Merged PR #28 to authoritative `main` as `1bf27785cf5502e32155d3d3d31bc5cbd052d3d6`.
- `/readyz` now requires at least one enabled external provider **and** explicit host-supplied `authority_transports_ready=true` before reporting ready.
- The authority-transport readiness signal defaults false and does not bypass per-request Identity or Privacy Shield verification.
- Exact-main CI run #78 / `35662686554` passed and Platform Contract run #20 / `35662687737` passed.
- Search remains Development/nonconformant; no live authority transport, approved external provider, deployment, Production Acceptance, or Stable qualification is established.

### September 21, 2026 — PR #27: main-state documentation reconciliation

- Reconciled documentation to the integrated authenticated Index-delegation boundary without runtime changes.
- Preserved the distinction between runtime-bearing exact revisions and later documentation-only checkpoints.
- Historical stacked branches remain provenance only and do not override `main`.

### September 21, 2026 — PR #24: roadmap reconciliation after authenticated Index boundary

- Reconciled the then-current roadmap to verified PR #23 integration.
- Documentation-only; did not connect live Identity/Privacy Shield services, approve an external provider, deploy Search, or change lifecycle.

### September 21, 2026 — PR #23: authenticated Index delegation HTTP boundary

- Integrated the bounded server-side Index delegation HTTP carrier.
- Added `/api/v1/status`, `/api/v1/search`, `/healthz`, and `/readyz`.
- Required injected GoreeCloud Identity requester verification and producer-authoritative Privacy Shield capability verification/consumption before query dispatch.
- Preserved the cycle-safe `goreecloud.search-index-delegation.v1` external-only/no-reentry/no-fallback contract.
- Capability evidence remained explicitly `production_accepted=false`.
- Exact candidate CI and Platform Contract checks passed; post-merge CI passed on the runtime-bearing revision recorded in repository notes.

### September 21, 2026 — PR #22: Platform Contract 0.4 reconciliation

- Migrated the repository control plane to Platform Contract 0.4 and declared exactly the nine Integral Platform Systems.
- Preserved lifecycle `development` and overall `nonconformant` state.
- Added the pinned repository Platform Contract workflow.
- Did not change Search runtime behavior or establish platform-system runtime acceptance.

### September 21, 2026 — PR #21: cycle-safe Index-originated Search delegation

- Added `goreecloud.search-index-delegation.v1` and `SearchCore.search_from_index(...)`.
- Forced Index-originated requests to external-only providers, prohibited Index/service/local provider re-entry, and prohibited fallback to Index.
- Preserved separate ordinary Search source modes for non-Index callers.
- Source/CI integration only; no live transport, credentials, approved provider, deployment, Production, or Stable claim.

## Migrated former root `CHANGELOG.md` state

The former singular changelog recorded the following implemented current-native foundations, all now represented in `IMPLEMENTED-FEATURES.md` and the current entries above:

- native query model/parser and privacy-aware planning;
- versioned Search ↔ Index contract and pagination;
- normalization/deduplication/source agreement/provenance;
- deterministic Search-owned ranking and result explanations;
- bounded asynchronous provider execution and failure isolation;
- query-disclosure budgets and source-plan evidence;
- cycle-safe Index-originated delegation; and
- the authenticated Index HTTP source boundary.

The former file explicitly made no release, deployment, Production Acceptance, or Stable claim; that boundary is preserved here.

## Drive retirement verification

Repository migration and Drive retirement are complete for the mapped Search feature/changelog sources:

1. PR #30 merged through protected `main` after exact-head CI and Platform Contract validation.
2. The three root records and the eight-part historical archive were read back from authoritative `main`.
3. Retired root `FEATURE-ROADMAP.md` and `CHANGELOG.md` were confirmed absent.
4. Exact-main CI and Platform Contract validation passed on the merged migration revision.
5. The two mapped Drive files were permanently deleted.
6. Independent post-deletion Drive reads returned `404 / not found` for both IDs.

Google Drive is no longer an active or mirrored Search feature/changelog authority. Other Search project/evidence records outside these two mapped feature/changelog files were not deleted by this migration.

## Maintenance rule

Record meaningful implementation, lifecycle, migration, security/privacy, compatibility, deployment, recovery, and release changes here with exact evidence where relevant. Preserve prior entries. Do not rewrite historical evidence merely because current architecture or lifecycle differs.
