# GoreeCloud Search

GoreeCloud Search is the privacy-first, self-hostable search and information-discovery service for the GoreeCloud ecosystem.

> **Lifecycle:** Development  
> **Version:** `0.1.0.dev14`  
> **Current scope:** Native query parsing, privacy-aware source planning, bounded provider execution orchestration, a versioned GoreeCloud Index contract boundary with pagination, cycle-safe Index-originated delegation, and a bounded authenticated Index HTTP boundary with injected Identity and Privacy Shield verifiers. No real credentials, approved live external provider, deployment, Production acceptance, or Stable qualification are established.

## What exists now

This repository currently contains the first native implementation foundation:

- A typed search-query model.
- Parsing for `site:`, `-domain:`, `filetype:`, `ext:`, `before:`, `after:`, `language:`, `region:`, `source:`, `category:`, and `lens:`.
- Quoted phrases and excluded terms.
- Search categories and deployment source modes.
- A deterministic source planner for Index First, Federated, GoreeCloud Only, External Only, and Offline / Local Index operation.
- A replaceable provider contract for GoreeCloud Index and future federated adapters.
- Bounded asynchronous provider execution with per-provider timeouts, cancellation propagation, concurrency limits, partial-failure isolation, fallback execution, and explicit availability state.
- Optional query-disclosure budgets that cap how many third-party providers may receive one query before execution begins.
- A privacy invariant that prevents external-provider inclusion in GoreeCloud Only and Offline / Local modes.
- Versioned Search ↔ GoreeCloud Index v1 contract models, transport-injected first-party adapter boundary, cursor pagination, and provider-reported degraded-state/warning propagation.
- Conservative URL canonicalization, canonical-URL/content-hash deduplication, source agreement, and result provenance.
- Deterministic ranking with inspectable scoring signals and human-readable result explanations.
- A bounded Index-originated HTTP boundary exposing `/api/v1/status`, `/api/v1/search`, `/healthz`, and `/readyz`; query execution requires an authenticated `goreecloud-index` requester plus a consumed `psc_*` Privacy Shield capability reference before `search_from_index(...)` can execute.
- Unit tests and pull-request CI.

The repository now contains a source-level authenticated Index HTTP boundary, but it is not automatically started or deployed. Identity and Privacy Shield authorities are injected interfaces; no credential issuer, signing key, reusable token, live verifier endpoint, production provider credential, or deployment configuration is embedded. The development CLI still performs no network access.

The October 5 stabilization topic combines pending HTTP/authority validation, bounded URL/display normalization, and provider batch limits from the current main baseline. It requires human security review and protected-branch acceptance. See [`NOTES.md`](NOTES.md#2026-10-05--concurrent-stabilization-candidate) for the verified scope, remaining limitations, and platform migration debt.

## Development use

Requires Python 3.11 or newer.

```bash
python -m pip install -e .
goreecloud-search parse 'privacy "search engine" site:example.com category:docs'
```

The command prints the parsed query as JSON. It performs no network access.

Run tests with:

```bash
python -m unittest discover -s tests -v
```

## Architecture direction

The intended separation is:

```text
Browser / AI / API clients
          |
          v
   GoreeCloud Search
   - query parser
   - source planner
   - privacy boundary
   - provider executor
   - normalization
   - deduplication
   - ranking
          |
     +----+----+
     |         |
     v         v
GoreeCloud   optional
  Index      providers
```

The current development candidate implements the query/parser, source-planning, bounded provider execution, Search ↔ Index contract/pagination, normalization/deduplication, initial deterministic ranking, and the fail-closed authority-readiness boundary. See [`IMPLEMENTED-FEATURES.md`](IMPLEMENTED-FEATURES.md) for verified current behavior, [`PLANNED-FEATURES.md`](PLANNED-FEATURES.md) for open product/acceptance obligations, and [`CHANGELOGS.md`](CHANGELOGS.md) for current and historical change records.

## Cycle-safe Index-originated delegation

Search now has a dedicated source-level `SearchCore.search_from_index(...)` path for a future request that originates from GoreeCloud Index. This path is deliberately different from Search's ordinary `INDEX_FIRST` behavior:

- it always plans with `EXTERNAL_ONLY`;
- every selected step must be a primary `ProviderOrigin.EXTERNAL` provider;
- `GOREECLOUD_INDEX`, `GOREECLOUD_SERVICE`, and `LOCAL` providers are excluded;
- no fallback stage is permitted;
- an Index-only configuration, an Index-directed `source:` filter, or a zero third-party-disclosure budget fails before provider dispatch.

The source contract identifier is `goreecloud.search-index-delegation.v1`, with mode `external_only`, Index-provider re-entry disabled, and fallback disabled.

This prevents the architectural cycle `Index → Search → Index` at the Search planning/execution boundary. The current candidate adds a bounded HTTP carrier around that path, but it does **not** provide real Identity credentials, a live Privacy Shield verifier, an approved external provider, deployment, Production acceptance, or Stable qualification.

## Privacy boundary

The planning layer distinguishes third-party query disclosure, can apply an explicit per-query third-party-provider disclosure budget, and fails closed for source modes that prohibit disclosure. The Index HTTP boundary authenticates the requester through an injected GoreeCloud Identity verifier and requires producer-authoritative Privacy Shield capability-reference verification with `consume=true` after bounded request-shape validation and before Search execution. The execution layer still runs only externally originated providers admitted by the cycle-safe plan. Wardveil Security, live verifier transports, approved providers, target-runtime controls, deployment, and production acceptance remain separate blockers.

## Status integrity

A branch, pull request, passing CI run, configuration declaration, or documented plan does not mean a feature is released, deployed, production-accepted, or Stable.

## Current implementation expansion

The current Development candidate adds the bounded authenticated Index HTTP carrier around the accepted cycle-safe source contract and the PR #28 fail-closed runtime-readiness condition. It advertises a production-shaped `search.query` capability but explicitly sets `production_accepted=false`; live Identity/Privacy Shield verification transports, approved external provider execution, deployment, runtime Platform-System acceptance, Production, and Stable remain unestablished.
