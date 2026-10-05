# GoreeCloud Search — Planned Features

**Record type:** Repository planned/open feature inventory  
**Repository:** `GoreeCloud/search`  
**Lifecycle:** Development / nonconformant  
**Repository version:** `0.1.0.dev14`  
**Migration state:** Authoritative repository record on protected `main`; legacy Drive feature/changelog sources retired and independently verified absent on September 22, 2026.  
**Governance baseline:** `main` at `db15ea4c6e7e29c395204a94cad07d886f9242ff`, merged by PR #30 on September 22, 2026.  
**Governing standard:** Standard — Repository Feature Tracking and Changelog Governance v1.0, effective September 22, 2026.

## Purpose and migration sources

This file carries forward every material open, partial, deferred, blocked, acceptance-gated, or future capability from the retired roadmap model. It reconciles:

- former root `FEATURE-ROADMAP.md`;
- retired Drive `goreecloud-search-planned-features-and-capabilities.md` (file ID `1Ja7M0-aWvhg9Zis6WIqeqirD1wTGAl4w`);
- current repository specifications/features/notes; and
- verified current `main` state.

The Drive planned-capabilities record was broad product-direction history. Where it conflicted with newer verified repository state, current repository evidence controls current disposition while the historical scope is preserved here. That Drive file was deleted only after the repository migration merged, authoritative `main` readback succeeded, the retired root files were confirmed absent, and exact-main CI/Platform Contract validation passed; independent Drive readback now returns 404 for the retired ID.

Historical Draft PR #29 remains unmerged provenance; equivalent C0/DEL query-control hardening was replayed and accepted on current `main` by PR #34 (`66ff984b8dd79624a739ab6117c42a572dc44475`). Live Identity, Privacy Shield, provider, and target-runtime acceptance remain separate open obligations.

## Priority open obligations

### P0 — Live authority and Index runtime acceptance

- Connect the injected GoreeCloud Identity verifier to the producer-authoritative live Identity service and verify requester/authentication semantics in the target runtime.
- Connect the injected Privacy Shield capability verifier/consumer to the producer-authoritative live Privacy Shield service and verify exact capability claims, one-operation consumption, failure behavior, and target-runtime acceptance.
- Establish an approved live external-provider set for the cycle-safe Index-originated delegation path.
- Exercise the authenticated Index HTTP carrier against accepted live authority transports and approved providers without allowing Index re-entry or fallback.
- Keep `/readyz` fail-closed until host authority transports and at least one approved external provider are accepted; the host readiness signal must never replace per-request authorization.
- Complete representative target-runtime, client, privacy, security, recovery, and operational acceptance before any production claim.

### P0 — Result pipeline completion

- Integrate the bounded local snippet-generation foundation into accepted provider/result flows while preserving provider/document provenance. The helper now bounds source processing and output, records normalized-window offsets/truncation state, strips unsafe display controls, performs no I/O, and retains no full source text; provider adapters still need explicit authorized-text integration.
- Complete SafeSearch/content-policy hooks and administrator policy enforcement.
- Expand transparent ranking signals only when they remain inspectable, reproducible, privacy-preserving, and evidence-backed.
- Expand “Why this result?” explanations and source/provenance presentation.
- Add richer canonicalization/duplicate relationships where supported by authoritative Index/provider evidence.
- Define caching/freshness behavior, invalidation, staleness indicators, and query/result cache privacy controls.

### P0 — Federated provider system

- Mature the provider SDK/adapter lifecycle and compatibility/versioning contract.
- Require explicit provider capability, authentication, privacy, cost, latency, category, language, region, SafeSearch, pagination, and health declarations.
- Add approved external provider integrations only through reviewed adapters and secret-reference boundaries.
- Add bounded retry, rate, quota, cost, and provider-health controls beyond the current timeout/concurrency foundation.
- Preserve graceful degradation so one failed provider cannot fail the entire search.
- Keep external suggestions disabled unless explicitly enabled.
- Add provider revocation/disablement and fail-closed compatibility behavior.

## Product capability backlog migrated from the legacy specification

### Search categories and structured verticals

Current typed categories are a foundation. Planned category/vertical expansion includes Discussions, Forums, Social, Maps/Places, Shopping, Academic, Documentation, Source Code, Books, Podcasts, Music, People, Software/Packages, richer Images, Videos, News, and Files. Categories must appear only when an enabled/authorized source can serve them.

### GoreeCloud Index integration and source modes

- Mature Index as a first-party source for document candidates, titles, canonical URLs, extracted text, snippets, publication/crawl dates, language/content type, structured metadata, domain/site data, duplicate relationships, graph/quality signals, spam/safety classification, freshness, and cached/indexed versions where those fields are authoritatively available.
- Preserve user/admin source modes: Index First, Federated, GoreeCloud Only, External Only, and Offline / Local Index.
- Complete authenticated live Index transport and target-runtime acceptance for ordinary Search↔Index operation; the current adapter remains transport-injected only.
- Keep Search as the owner of user-facing query planning, normalization, deduplication, ranking, policy, and explanations rather than transferring those authorities to Index.

### Search syntax and power-user behavior

The current parser implements the initial operator set. Planned expansion includes complete Boolean/parenthetical semantics, domain-only/date-range flows, provider targeting, Lens selection, category shortcuts, and optional bang-like navigation with a clear distinction between Search-mediated queries and direct third-party redirects.

### GoreeCloud Lenses

Implement portable, transparent, exportable, shareable, optionally local-only user ranking rules for boosting, lowering, excluding, domain/category/language/file-format preferences, independent-publisher preferences, official-documentation preferences, archival/recency preferences, and similar user-controlled reranking without behavioral profiling.

### Privacy by default and search history

- Preserve no advertising profile, no sale of history, no cross-query identity profile, no click-tracking ranker, no mandatory third-party analytics, minimal request metadata, and privacy-preserving diagnostics.
- Keep persistent history optional.
- If history is implemented, support explicit retention/storage choices such as device-only, authorized encrypted Sync, self-hosted account storage, automatic expiration, manual retention, and private-search exclusion.
- Define privacy-safe query/session telemetry and diagnostic aggregation before collection.

### Private View / isolated browsing

Plan explicit privacy-preserving result-opening modes such as proxy retrieval, isolated GoreeCloud Browser context, or remote rendering. Any implementation must separately govern IP/cookie/storage/fingerprint/referrer/session isolation and require explicit transitions for sensitive actions such as login, payment, downloads, camera, or microphone.

### GoreeCloud Browser integration

- Address-bar search through GoreeCloud Search.
- New-tab Search integration.
- Dedicated expanded Search page/surface.
- User-controlled suggestions from local history, Index, self-hosted Search, or explicitly enabled external suggestions.
- Clear Search-unavailable/degraded state without silent third-party fallback.
- Result actions such as open/new tab/private/container/save/share/copy/search-site/block/boost/add-to-Lens when authorized.
- Browser/OpenSearch compatibility with explicit privacy/logging review for GET-based protocols.

### Result experience

Planned user-facing results may expose favicon, domain/site, title, canonical URL, snippet, publication date, content type, source indicators, privacy/security indicators, Index state, cached/archive state, and labels such as Indexed by GoreeCloud, External Source, Multiple Sources, Cached, Archived, Discussion, Official Source, PDF, and Recently Updated when evidence supports them.

### Discussions, Quick Answers, and optional AI answers

- Discussions/community-result surfaces that distinguish official information, news, forums, reviews, Q&A, and personal experience.
- Non-generative Quick Answers for high-confidence structured data with explicit sources.
- Optional GoreeCloud AI synthesis above Search—not as a replacement for ordinary results—with bounded retrieved evidence, inline citations, source lists, dates, and links to originals.
- Preserve explicit least-capability escalation from Search → Fetch → Research → Agent/Browser.

### SafeSearch and content controls

Support Off/Moderate/Strict modes plus administrator allow/block rules, adult-content policy, malware/phishing/unsafe-download warnings, and organization-defined policy. Wardveil Security may supply authoritative safety evidence but must not silently become the Search ranking authority.

## Self-hosting, deployment, and production hardening

### Distribution profiles

Plan supported deployment paths for OCI/Docker, rootless Podman/Quadlet, GoreeCloud Containers, justified Kubernetes/Helm, and bare-metal service definitions on supported Linux architectures.

### Container and artifact security

- Non-root/minimal runtime where practical.
- Read-only filesystem and explicit writable volumes.
- Dropped capabilities and `no-new-privileges`.
- Health/readiness endpoints tied to truthful runtime authority state.
- Secret references rather than embedded credentials.
- Signed artifacts/images, SBOM, provenance, checksums, and reproducible build metadata before Stable qualification.
- Immutable deployment identities and tested rollback/recovery.

### Deployment profiles

Retain personal, private Search+Index, hybrid, and organization/cluster deployment models as planned product profiles. Current native `main` does not establish a production deployment of these profiles.

## Administration, API, preferences, and observability

### Administration

Plan provider controls, source modes, categories, limits, health, rate/cost budgets, SafeSearch/content policy, Index connectivity, platform-system status, and deployment diagnostics without exposing protected query/content data unnecessarily.

### Public / client Search API

- Versioned client-facing Search API with explicit schemas, bounded request/result sizes, authentication/authorization, rate/abuse controls, compatibility policy, and deprecation rules.
- Keep machine-readable formats disabled until the applicable access, monitoring, abuse, privacy, and versioning gates are accepted.

### Preferences

Plan explicit Search, Privacy, and Appearance preferences, including source mode, categories, provider controls, SafeSearch, Lenses, history, suggestions, private opening behavior, language/region, result density, theme, reduced effects, and accessibility settings as applicable.

### Privacy-safe observability

- Metrics/health/readiness that avoid query or credential disclosure.
- Correlation/request identifiers that do not become cross-query identity profiles.
- Bounded aggregate quality/reliability evidence.
- Explicit retention and access controls for logs/diagnostics.

## Integral Platform Systems and ecosystem integration

### Nine Integral Platform Systems

Complete evidence-backed integration and acceptance, where applicable, for GoreeCloud Manager, Privacy Shield, Wardveil Security, Everkeep, Glaze UI, GoreeCloud Mesh, GoreeCloud Identity, GoreeCloud Policy, and GoreeCloud Observability. Unsupported/unverified states must remain blocked/nonconformant rather than omitted or promoted.

### GoreeCloud Mesh

Plan service/capability discovery, endpoint selection, health/capability metadata, and revocation/availability behavior without letting discovery grant authorization.

### GoreeCloud Identity

Complete live requester/user/service identity verification, scopes/claims, expiration, revocation, and audit-safe failure behavior. Authentication must not imply authorization beyond the exact Search operation.

### Privacy Shield

Complete producer-authoritative query-disclosure/capability policy, purpose binding, one-operation capability consumption, retention controls, and explicit third-party disclosure decisions.

### Wardveil Security

Plan provider/domain/result safety evidence, abuse/threat controls, and policy enforcement while preserving Search ranking-authority boundaries.

### Everkeep

Plan configuration/state backup, migration, restore validation, and disaster-recovery evidence for applicable Search state without backing up secrets in unsafe form.

### GoreeCloud Manager

Plan read/admin surfaces for Search service status, provider state, policy, health, diagnostics, and lifecycle controls with role separation and protected-data boundaries.

### GoreeCloud Sync

If Search preferences/history/Lenses are synchronized, define versioned records, authentication, conflict/merge semantics, privacy/retention rules, and local-disable behavior. Sync remains separately governed and is not a tenth Integral Platform System.

## Architecture and reliability backlog

- Keep Search stateless wherever practical; isolate any required state and migration/recovery semantics.
- Define Search sessions without turning them into hidden long-lived behavioral profiles.
- Complete graceful degraded modes, partial-result presentation, retry behavior, and user-facing availability semantics.
- Define provider/query caches, freshness, invalidation, privacy, and offline behavior.
- Preserve strict separation among Search, Index, Browser, AI, and platform authorities.

## Internationalization, accessibility, quality, and testing

### Internationalization/localization

Plan locale-aware UI, language/region filters, result metadata, date/number presentation, RTL behavior, translation governance, and provider capability negotiation without silently changing privacy/source policy.

### Accessibility and input methods

Complete keyboard-only, screen-reader, Switch Access, D-pad, touch, high contrast, forced colors, reduced motion/transparency, large text/zoom, and responsive/adaptive acceptance for any user-facing Search surface.

### Search quality evaluation

Build reproducible evaluation sets and metrics for relevance, diversity, duplication, freshness, source coverage, latency, degradation, unsafe content, and explanation quality without relying on behavioral advertising profiles.

### Testing and acceptance

Maintain unit, contract, integration, security/privacy, interoperability, recovery, performance, accessibility, browser/device, representative-provider, and target-runtime test layers with exact-revision evidence and clear non-claims.

## Data portability, developer interfaces, and private corpora

- Versioned export/import for applicable preferences, Lenses, history, provider configuration, and other portable user/admin state.
- Schema evolution and compatibility/deprecation rules for provider and client APIs.
- Stable developer/CLI interfaces for diagnostics and controlled automation without bypassing privacy/authorization gates.
- Private/internal corpus search with explicit authorization, tenant/user isolation, source provenance, and no cross-boundary leakage.
- Search workspaces/research sessions only as explicit user-created contexts with bounded retained state and clear escalation to deeper research tooling.

## Release and Stable qualification

Before Release Candidate, Production, or Stable claims:

- exact source/artifact identity and required CI must be green;
- required Platform Contract and runtime platform-system gates must pass;
- live authority and provider integrations must be accepted;
- security/privacy/abuse review must pass;
- representative performance/reliability/accessibility/client/runtime evidence must pass;
- backup/recovery/rollback must be tested;
- signing, provenance, SBOM/checksums, release notes, upgrade/migration documentation, and deployment evidence must be complete;
- repository records must be reconciled to the exact accepted revision.

## Roadmap migration disposition

The former root roadmap's phases are preserved as follows:

| Former phase | New disposition |
| --- | --- |
| Phase 0 — Native foundation | Implemented portions → `IMPLEMENTED-FEATURES.md`; remaining parser/planner/provider acceptance and lifecycle work retained above. |
| Phase 1 — GoreeCloud Index path | Contract/cycle-safe/HTTP foundations implemented; live authority/runtime acceptance retained as P0. |
| Phase 2 — Search result pipeline | Normalization/dedupe/ranking/provenance foundations implemented; snippet/SafeSearch/advanced quality work retained. |
| Phase 3 — Federated providers | Execution/disclosure foundations implemented; provider lifecycle/integrations/health/rate/cost controls retained. |
| Phase 4 — Service API/platform controls | HTTP/health/readiness source foundations implemented; live Identity/Privacy Shield and other platform integration retained. |
| Phase 5 — Browser and Glaze UI | Planned in current native line. Historical earlier UI evidence remains provenance only. |
| Phase 6 — Advanced discovery | Planned. |
| Phase 7 — Production/self-hosting | Planned for current native line; historical deployments/releases do not establish current-native production acceptance. |

The former Drive-sync roadmap obligation is superseded by repository-native governance. Google Drive is no longer an active or mirrored feature/changelog authority for Search; both mapped legacy feature/changelog file IDs were deleted after the repository deletion gate passed and now return 404.

## Maintenance rule

A capability remains here until its defined implementation and acceptance scope is complete. When completed, reconcile `IMPLEMENTED-FEATURES.md`, this file, and `CHANGELOGS.md` in the same evidence-backed change. Do not promote Draft PRs, green CI on unmerged heads, historical deployments, or documentation-only state into current implementation authority.
