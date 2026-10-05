# GoreeCloud Search — Repository Notes

## Current development baseline

Current authoritative `main` is `66ff984b8dd79624a739ab6117c42a572dc44475` (merged PR #34 on September 22, 2026). Exact-main CI #87 / `35791305078` and Platform Contract #29 / `35791305711` passed on that revision. Search remains Development/nonconformant: live GoreeCloud Identity and Privacy Shield verifier transports, an approved external provider, deployment, representative runtime acceptance, Production Acceptance, and Stable qualification remain open.

Repository-governance PR #30 merged as `db15ea4c6e7e29c395204a94cad07d886f9242ff`. Exact-main CI run #81 / `35732002017` and Platform Contract run #23 / `35732002972` passed on that merged documentation/governance revision. `IMPLEMENTED-FEATURES.md`, `PLANNED-FEATURES.md`, and `CHANGELOGS.md` are now authoritative repository records; former root `FEATURE-ROADMAP.md` and `CHANGELOG.md` are retired.

The two mapped legacy Drive feature/changelog sources were deleted only after the repository migration deletion gate passed. Independent Drive readback now returns 404 for `Change Log — Search.docx` (`1uEAtCFrxl8D3HnVxzRInMe92lRAiJKBv`) and `goreecloud-search-planned-features-and-capabilities.md` (`1Ja7M0-aWvhg9Zis6WIqeqirD1wTGAl4w`). Google Drive is no longer an active or mirrored Search feature/changelog authority.

Historical Draft PR #29 remains unmerged provenance; equivalent C0/DEL query-control hardening was independently replayed and accepted through PR #34 on current `main`.

The bounded snippet-generation source foundation processes only already-authorized plain text, performs no network or filesystem I/O, caps retained output, removes unsafe display controls, and does not itself grant provider/content-fetch authority. Provider/result integration remains a separate acceptance obligation.

## Design decisions

- Python 3.11+ is used for the initial core because the slice requires no runtime third-party dependencies and can be validated quickly.
- Provider execution is separated behind a protocol so GoreeCloud Index and optional external sources can be integrated without coupling the parser/ranking core to a specific provider.
- The executor is intentionally policy-following rather than provider-selecting: only source-plan-approved providers can run.
- Provider exceptions and timeouts become explicit execution state; caller cancellation propagates and cancels in-flight work.
- Index-first fallback is conditional and cannot bypass planner privacy policy.
- No external provider is silently substituted when a privacy-restrictive source mode is selected.
- This version is Development only.

## Index-originated cycle-safety decision

The dedicated Index-originated path is intentionally not the ordinary Search `INDEX_FIRST` path. It is fixed to external-only planning so an Index request cannot be routed back into the GoreeCloud Index provider or another first-party/local provider and cannot fall back into Index after an external failure.

The cycle-safe contract and its bounded authenticated HTTP carrier are accepted on authoritative `main`. The HTTP boundary requires an authenticated `goreecloud-index` application identity through an injected Identity verifier and an opaque `psc_*` Privacy Shield capability reference through an injected producer-authoritative verifier/consumer before dispatch. No live verifier service, real credential, approved external provider, deployment, or Production acceptance is implied.

Authoritative `main` also carries the accepted Platform Contract 0.4 nine-system declaration from PR #22. Runtime Platform-System acceptance remains separate and blocked.

## 2026-09-21 — Fail-closed runtime readiness integrated

PR #28 merged the runtime-readiness condition into authoritative `main`. The Index-originated HTTP server requires an explicit host-supplied `authority_transports_ready` acceptance signal in addition to at least one enabled external provider before `/readyz` can return ready. The default is false. This prevents source-level provider configuration from overstating runtime readiness while live GoreeCloud Identity and Privacy Shield verifier transports remain unaccepted. The signal does not bypass per-request Identity or Privacy Shield verification and does not itself establish production acceptance.

## 2026-09-22 — Repository feature/changelog migration and Drive retirement

PR #30 moved Search feature/changelog authority into the protected repository root, migrated all 77 dated legacy Drive changelog entries into eight provenance archives, retired the legacy root roadmap/singular changelog, reconciled current README/notes, and added a governance regression test. After exact-main readback and validation, the two mapped Drive feature/changelog files were deleted and independently verified absent. This was documentation/governance work only and did not change runtime or lifecycle state.

## Open decisions

- Final production service/runtime framework.
- Public source licensing/rights model.
- Approved production provider set.
- Exact current Stable Platform-System contract versions at the time each integration is implemented.
- Production deployment topology and persistence model.

## Historical stacked implementation provenance

Earlier normalization, ranking, provider-execution, disclosure-budget, maintained-fork, release-candidate, native-rebuild, Sync, Glaze, and deployment branches are development or historical staging evidence. Their accepted behavior must be evaluated against the current native repository line; historical branch/lifecycle state must not override current `main`.

The feature/changelog migration preserves the retired Drive chronology under `docs/changelog-history/` for this reason.

## Ranking baseline

The initial ranker intentionally avoids provider-specific hidden boosts and behavioral signals. GoreeCloud Index presence is recorded as provenance but contributes zero score. Source agreement is bounded so federation consensus cannot dominate lexical/query-intent relevance.

## Query-disclosure budget

The budget is enforced in source planning, before execution. It can reduce or eliminate third-party providers but cannot add a provider that the selected source mode, category, source filter, or provider configuration would otherwise exclude. A zero budget prevents external fallback execution rather than contacting an external provider and discarding its response afterward.

## 2026-09-21 — Authenticated Index transport integrated

PR #23 integrated the server-side HTTP half of Index → Search delegation while preserving `goreecloud.search-index-delegation.v1`, `external_only`, no Index re-entry, and no fallback. GoreeCloud Identity and Privacy Shield remain injected producer-authoritative verifier interfaces. Capability evidence is production-shaped but explicitly `production_accepted=false`.

Post-merge CI run `35625485445` passed on exact runtime-bearing revision `7d79959e79ad4de13b807973347944bd92563fbe`. Later accepted PRs #24, #27, and #28 advanced documentation/readiness behavior without converting those injected interfaces into accepted live authority transports. No live verifier, approved external provider, deployment, Production acceptance, or Stable qualification is implied.
