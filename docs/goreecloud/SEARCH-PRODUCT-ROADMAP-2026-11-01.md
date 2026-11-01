# GoreeCloud Search — Product Roadmap

**Mission:** A privacy-first, self-hostable, federated information discovery service with native Linux and responsive web clients, using the GoreeCloud UI authority.

## P0 — Recovery and honest baseline

- [ ] Re-establish public `GoreeCloud/search` repository from reviewed snapshot.
- [ ] Verify successful clean checkout, offline tests, and GitHub CI after publication.
- [ ] Investigate unrecovered 2026-10-24–27 changes without overwriting this baseline.
- [ ] Classify actual live deployment and SearXNG/provider compatibility separately.
- [ ] Preserve SearXNG AGPL attribution, NOTICE, LICENSE and upstream references.

## P1 — Trustworthy everyday search

- [ ] Verify POST-first query submission and safe HTTP(S) result links.
- [ ] Explicit per-provider opt-in/opt-out, timeout, partial failure and provenance.
- [ ] Stable category navigation for Web, Images, Videos and News.
- [ ] Deduplication, sort/ranking, snippets, pagination and filters with regression tests.
- [ ] Prevent query leakage in URLs, logs, analytics, and cross-site redirects.
- [ ] GC UI migration (from historical Glaze styling), contrast and keyboard acceptance.

## P2 — Expand supported sources without false completeness

- [ ] Academic/research, developer, documents, music, public social and map/provider adapters.
- [ ] Result metadata and citations only where supported by providers; no fabricated completeness.
- [ ] SafeSearch, language/region/date filtering with explicit provider-support status.
- [ ] Personal preferences, local-only mode, isolated credentials and documented retention.
- [ ] JSON API/OpenAPI plus browser search, RSS/CSV only where access policy allows.
- [ ] Open Chat search-tool integration with scoped auth, read permissions and attribution.

## P3 — Optional intelligence and operations

- [ ] Source-grounded answer generation as an optional external AI capability, with transparent citations.
- [ ] Ranking/reranking extensions without hidden query disclosure.
- [ ] Admin health and per-provider diagnostic surface; rate limits, metrics and privacy-preserving logs.
- [ ] Packaged native Linux, container and private HTTPS deployment with restoration tests.
- [ ] Accessibility, responsive screenshots, privacy/security review, performance budgets and release gates.

## Architecture boundaries

Clients (native Linux and web) → Search gateway (query validation, credential-aware policy, rate limits) → Concurrent SearXNG provider adapters → normalized results and source attribution. Future specialized adapters and optional AI layer must be modular. The local SQLite FTS5 native index is **separate and opt-in** unless independently qualified for federation.

No login required for basic private search; account sync/enterprise identity and AI must be optional and separately reviewed. External providers can receive submitted queries and the server public IP unless a verified proxy is configured. The app must never promise anonymity without network/runtime evidence.

## Acceptance matrix

| Domain | Minimum evidence |
| --- | --- |
| Search | Deterministic offline fixtures, tested deduplication and partial failures |
| Privacy | Verified POST/redirect/URL validation, no secret in checked-in code or ordinary logs |
| UI | GC UI tokens, dark/light, keyboard, mobile, error and empty states |
| Integrations | Schema/contract tests, scoped API auth and provider health metadata |
| Operations | Live private staging smoke, health checks, metrics without user queries, rollback |
| Release | Reproducible build, license review, CI, signed/recoverable artifact when applicable |

**Status:** This roadmap is proposed work. Checked boxes must be marked only after source/CI evidence.
