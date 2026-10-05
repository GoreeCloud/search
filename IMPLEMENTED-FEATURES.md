# GoreeCloud Search — Implemented Features

**Record type:** Repository implemented-feature inventory  
**Repository:** `GoreeCloud/search`  
**Lifecycle:** Development / nonconformant  
**Repository version:** `0.1.0.dev14`  
**Migration state:** Authoritative repository record on protected `main`; legacy Drive feature/changelog sources retired and independently verified absent on September 22, 2026.  
**Governance baseline:** `main` at `db15ea4c6e7e29c395204a94cad07d886f9242ff`, merged by PR #30 on September 22, 2026.  
**Governing standard:** Standard — Repository Feature Tracking and Changelog Governance v1.0, effective September 22, 2026.

## Interpretation

This record describes behavior implemented in the current native GoreeCloud Search Development source. It does **not** claim a deployed service, approved live external provider, producer-authoritative live Identity or Privacy Shield transport, Production Acceptance, Release Candidate, or Stable qualification.

A partially implemented capability can appear here for the verified portion that exists and in `PLANNED-FEATURES.md` for the remaining work. Historical maintained-fork, release-candidate, deployment, native-rebuild, and prior-repository evidence is preserved under `docs/changelog-history/`; historical lifecycle claims do not override current `main`.

Draft or unmerged pull requests are not implementation authority. Historical Draft PR #29 remains unmerged provenance; equivalent query-control hardening was independently replayed and merged as PR #34 on current `main`.

## Current verified Development baseline

PR #28 established the earlier readiness baseline at `1bf27785cf5502e32155d3d3d31bc5cbd052d3d6`. Current authoritative `main` is `66ff984b8dd79624a739ab6117c42a572dc44475`, merged through PR #34 after PR #33 corrected the repository identity. Exact-main CI #87 / `35791305078` and Platform Contract #29 / `35791305711` passed on that current revision.

Repository-governance PR #30 then merged as `db15ea4c6e7e29c395204a94cad07d886f9242ff`; exact-main CI run #81 / `35732002017` and Platform Contract run #23 / `35732002972` passed. PR #30 changed documentation/governance only and did not alter Search runtime behavior.

The current line remains Development/nonconformant. The host-supplied authority-transport-readiness signal defaults false and cannot replace per-request GoreeCloud Identity or Privacy Shield verification.

## Implemented capabilities

### Native query model and parsing

- Native Python package under `src/goreecloud_search` with Python 3.11+ support.
- Typed query, search-category, source-mode, provider, execution, and result models.
- Free-text terms, double-quoted phrases, and excluded terms.
- Initial operators for `site:`, `-domain:`, `filetype:`, `ext:`, `before:`, `after:`, `language:`, `region:`, `source:`, `category:`, and `lens:`.
- ISO date validation and normalized repeatable filters.
- Development CLI for query parsing without network access.

### Privacy-aware source planning

- Deterministic planning for Index First, Federated, GoreeCloud Only, External Only, and Offline / Local Index modes.
- Fail-closed exclusion of third-party providers from GoreeCloud Only and Offline / Local modes.
- Explicit third-party query-disclosure classification.
- Optional per-query disclosure budgets that cap the number of third-party providers before execution begins.
- Source-plan evidence for admitted third-party provider count, applied disclosure budget, and providers omitted by the budget.
- Deterministic provider eligibility by configured capability, category, source policy, and origin.

### Provider execution and degradation

- Replaceable typed provider protocol and provider search batches.
- Bounded asynchronous execution with configurable per-provider timeout and maximum concurrency.
- Caller-cancellation propagation to in-flight provider work.
- Provider failure isolation and explicit `available`, `degraded`, and `unavailable` states.
- Index-first fallback only when the primary stage does not fill the requested raw-result target.
- Fail-closed rejection of provider batches that spoof another provider's provenance.
- End-to-end core flow from parse → plan → execute → normalize/deduplicate → rank.

### GoreeCloud Search ↔ Index contract

- Versioned `goreecloud.search-index.v1` request/response contract boundary.
- First-party Index adapter with injected transport rather than an embedded live transport.
- Category/capability negotiation and bounded page-size behavior.
- Cursor pagination with repeated-cursor protection.
- Index degraded-state and warning propagation into Search execution state.
- Result provenance fields needed for Search-owned normalization, ranking, and explanation.

### Cycle-safe Index-originated delegation

- Dedicated `goreecloud.search-index-delegation.v1` path for future Index-originated requests.
- Fixed external-only planning for that path.
- Explicit prohibition on `GOREECLOUD_INDEX`, `GOREECLOUD_SERVICE`, and `LOCAL` provider execution for Index-originated delegation.
- No fallback stage and no recursive Index re-entry.
- Fail-closed behavior when source filtering or disclosure policy leaves no valid external provider.

### Authenticated Index HTTP source boundary

- Bounded server-side endpoints `/api/v1/status`, `/api/v1/search`, `/healthz`, and `/readyz`.
- Strict JSON/body/request bounds for the Index delegation carrier, including accepted C0/DEL query rejection before authentication/provider execution on current `main`.
- Injected GoreeCloud Identity bearer/requester verification requiring the expected `goreecloud-index` caller identity before query dispatch.
- Injected Privacy Shield opaque capability-reference verification and consumption before provider execution.
- Generic fail-closed authorization errors that do not disclose verifier internals.
- Production-shaped capability evidence that remains explicitly `production_accepted=false`.
- `/readyz` requires both at least one enabled external provider and an explicit host-supplied `authority_transports_ready=true` signal; the signal defaults false.
- The readiness signal does not bypass per-request Identity or Privacy Shield verification.

### Result normalization, deduplication, and ranking

- Enriched result candidates with canonical URL, source ID, content hash, language, crawl timestamp, and provider-contract provenance.
- Conservative URL canonicalization.
- Canonical-URL and content-hash deduplication.
- Multi-provider source-agreement counts and provenance aggregation.
- Fail-closed rejection of candidates from undeclared providers.
- Deterministic Search-owned ranking using inspectable query/result evidence.
- Bounded signals for quoted phrases, title/snippet terms, explicit site/filetype/language matches, and source agreement.
- Per-result ranking-signal records and human-readable “Why this result?” explanations.
- No advertising-payment ranking, click-history profile, hidden provider-specific boost, or cross-query behavioral profile in the implemented ranker.

### Bounded local snippet-generation foundation

- Deterministic query-aware snippet generation for plain text the caller is already authorized to process.
- Source processing is capped at 32,768 Unicode characters and generated output is capped at 280 characters.
- Query phrases/terms can focus the selected window; no-match generation prefers a complete leading sentence when it fits.
- Generated evidence records normalized-source offsets, query-match state, and source-truncation state without retaining full source text.
- C0/C1 controls and Unicode bidirectional formatting controls are removed from snippet presentation input.
- The helper performs no network or filesystem I/O and grants no content-fetch authority.
- Provider/result-pipeline integration remains acceptance-gated and is retained in `PLANNED-FEATURES.md`.

### Repository and platform control plane

- GoreeCloud Platform Contract 0.4 declaration covering the nine Integral Platform Systems while preserving Development/nonconformant state for unresolved runtime integrations.
- Repository CI on Python 3.11 and 3.12.
- Platform Contract validation workflow pinned to the governed reusable validator revision used by the accepted control-plane change.
- Explicit internal application version and Development lifecycle documentation.
- Repository-native implemented/planned/changelog governance with a regression test that requires the three root records and rejects the retired root roadmap/singular changelog filenames.

## Implemented-but-not-accepted boundaries

The following source foundations exist but remain acceptance-gated and therefore also appear in `PLANNED-FEATURES.md`:

- Index transport models without producer-authoritative live Index runtime acceptance.
- Identity and Privacy Shield verifier interfaces without accepted live verifier transports.
- Health/readiness surfaces without production runtime acceptance.
- Provider execution infrastructure without an approved live external provider set.
- Ranking/explanation foundations without the complete planned quality, vertical, SafeSearch, and user-experience scope.

## Explicitly not implemented on current `main`

Current authoritative `main` does not establish:

- an approved live external Search provider or production provider credential;
- live GoreeCloud Identity or Privacy Shield verifier-service transport;
- Wardveil Security runtime enforcement;
- GoreeCloud Mesh discovery/runtime integration;
- GoreeCloud Manager administration;
- a user-facing Search web/Glaze UI surface in the current native line;
- GoreeCloud Browser address-bar/new-tab integration;
- Private View;
- persistent search history or accepted GoreeCloud Sync integration;
- GoreeCloud AI answer synthesis;
- production deployment artifacts or an active deployment of this current native line;
- Production Acceptance, Release Candidate, or Stable qualification.

## Legacy-source retirement

The former Drive `Change Log — Search.docx` (`1uEAtCFrxl8D3HnVxzRInMe92lRAiJKBv`) and `goreecloud-search-planned-features-and-capabilities.md` (`1Ja7M0-aWvhg9Zis6WIqeqirD1wTGAl4w`) were deleted only after PR #30 merged, the replacement records/history were read back from protected `main`, the retired root files were confirmed absent, and exact-main validation passed. Independent Drive readback now returns 404 for both retired IDs.

## Maintenance rule

When a planned obligation is implemented and verified on the authoritative integration line, reconcile it here, update/remove its open disposition in `PLANNED-FEATURES.md`, and record the meaningful change in `CHANGELOGS.md`. Passing CI on an unmerged branch is not sufficient implementation authority.
