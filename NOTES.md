# GoreeCloud Search — Repository Notes

## Current development baseline

Authoritative `main`, verified October 5, 2026, is `39c1eec1851b0b11a3ecc4277ebc78f608b989d1` (PR #38 evidence migration). The latest runtime-bearing Search baseline is `66ff984b8dd79624a739ab6117c42a572dc44475` (PR #34 query-control hardening). Exact-main [CI run `36358514424`](https://github.com/GoreeCloud/search/actions/runs/36358514424) and [Platform Contract run `36358514745`](https://github.com/GoreeCloud/search/actions/runs/36358514745) passed on `39c1eec1851b0b11a3ecc4277ebc78f608b989d1`. Search remains Development/nonconformant: live GoreeCloud Identity and Privacy Shield verifier transports, an approved external provider, deployment, representative runtime acceptance, production acceptance, and Stable qualification remain open.

Repository-governance PR #30 merged as `db15ea4c6e7e29c395204a94cad07d886f9242ff`. Exact-main CI run #81 / `35732002017` and Platform Contract run #23 / `35732002972` passed on that merged documentation/governance revision. `IMPLEMENTED-FEATURES.md`, `PLANNED-FEATURES.md`, and `CHANGELOGS.md` are now authoritative repository records; former root `FEATURE-ROADMAP.md` and `CHANGELOG.md` are retired.

The two mapped legacy Drive feature/changelog sources were deleted only after the repository migration deletion gate passed. Independent Drive readback now returns 404 for `Change Log — Search.docx` (`1uEAtCFrxl8D3HnVxzRInMe92lRAiJKBv`) and `goreecloud-search-planned-features-and-capabilities.md` (`1Ja7M0-aWvhg9Zis6WIqeqirD1wTGAl4w`). Google Drive is no longer an active or mirrored Search feature/changelog authority.

PR #29 remains historical Draft provenance. Equivalent C0/DEL query-control hardening is accepted through PR #34; unmerged PR #35 and PR #37 work is carried forward by the October 5 stabilization candidate, not by treating their old checks as current-main authority.

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

Authoritative `main` also carries the legacy Platform Contract 0.4 nine-system declaration from PR #22, with the repository identity corrected by PR #33. The active System-Wide Platform Contract instruction is v2.0 and uses `seed`, `lab`, `forge`, `weave`, `seal`, `anchor`, `sunset`, and `archive`. The repository declaration and pinned validator require a staged compatibility migration before changing schema/lifecycle values. Passing the old validator does not establish current-governance or runtime Platform-System acceptance.

## 2026-10-05 — Concurrent stabilization candidate

Three bounded workstreams were integrated from the verified main baseline: HTTP request/authority handling, result URL/display normalization, and provider batch shape/cardinality validation. PR #35 and PR #37 source/test behavior was preserved and extended; PR #36 snippet generation remains a separate pending feature.

- HTTP input rejects duplicate authority/media/length headers, transfer encoding, invalid or oversized ports, incomplete declared bodies, and query controls/surrogates before authorization or provider calls. Socket reads have a five-second timeout. Identity and Privacy verification require typed records, exact requester/consumer identities, and explicit `True` authorization/consumption decisions; malformed records return generic 401 errors.
- Host and URL normalization supports canonical DNS/IPv4, bracketed IPv6, and a conservative NFC/IDNA roundtrip subset. It rejects ambiguous numeric hosts, scoped IPv6, credentials, unsafe schemes, invalid A-labels, and IDN mappings that change host identity. This does not claim complete IDNA2008 support. Actual navigation URLs are validated even when a supplied canonical alias is safe.
- URL input is capped at 8192 characters. Display source fields are capped at 32768 characters; sanitized titles/snippets are capped at 512/4096. C0/C1 and bidi display controls are removed, surrogate input is rejected, and ordinary emoji joiners are preserved.
- Provider batches must have the expected record/tuple/boolean/text shapes and may not return more candidates than the actual requested limit, including a reduced fallback limit. Shared normalization validates URL/display content inside the provider's failure boundary before its batch is admitted. Shape/count/type/content failures become generic provider errors, preserving healthy federation and permitted fallback. All-invalid Index delegation stays unavailable and later requests can recover.
- Raw validated candidates remain available for central cross-provider deduplication, provenance aggregation, and ranking. The shared pure normalization rules run once for each bounded provider batch and again centrally; this adds bounded CPU work and avoids a separate content policy. Validation occurs after an adapter returns and does not bound allocations or network bytes inside an adapter.

Local Python 3.12.14 compilation and all 112 unit tests passed on the combined candidate. Independent AI re-review also passed the HTTP and provider content-isolation regressions; this is separate from the required human review. Exact-head CI and review status are tracked in the candidate PR. These are source-candidate evidence only. The laptop has Python 3.10.12, below the package's Python 3.11 minimum, so target-device execution is blocked. No runtime install, live provider activation, deployment, or lifecycle promotion was performed.

Human security review is required before protected-branch acceptance under [Instruction — Secure Coding](https://docs.google.com/document/d/1Z1OEJYopW1ytZcyG4TuaBvF4VwJSkyt3/edit): “Human review is mandatory when AI-generated work affects important trust boundaries.” Independent AI review and passing checks do not satisfy that gate.

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
