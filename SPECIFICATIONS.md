# GoreeCloud Search — Repository Specifications

## Lifecycle

- Product: GoreeCloud Search
- Version: `0.1.0.dev14`
- Lifecycle: Development
- Stable: No

## Current implementation boundary

The current native development candidate provides a query parser and privacy-aware source planner, bounded asynchronous provider execution, pre-execution third-party query-disclosure budgeting, a versioned Search ↔ Index contract boundary with pagination, a cycle-safe Index-originated delegation path, a bounded authenticated Index HTTP source boundary, Search-owned normalization/deduplication primitives, and an initial deterministic ranking layer.

### Query model

The parser supports free-text terms, double-quoted phrases, excluded terms (including `-"excluded phrase"`), `site:`, `-domain:`, `filetype:`, `ext:`, `before:`, `after:`, `language:`, `region:`, `source:`, `category:`, and `lens:`. Quoted operator-like text remains a literal phrase, and malformed/unbalanced quotation is rejected.

The query-filter-correctness candidate applies `site:` and filetype constraints plus excluded domains against normalized canonical URLs, and excluded words/phrases against normalized visible result title/snippet, before deterministic ranking. This is a post-provider display/result constraint only: it does not constrain provider-side query disclosure, unseen document text, access permissions, or raw-result fallback counting. The candidate may return fewer results than the requested limit after filtering. Language remains a ranking preference, and date, region, lens, and other not-yet-integrated semantics are not falsely represented as fully enforced.

### Source modes and privacy invariant

The source planner implements `index_first`, `federated`, `goreecloud_only`, `external_only`, and `offline_local`. It never executes a provider. The executor may run only providers named by the returned plan and must not discover or substitute additional sources. `goreecloud_only` and `offline_local` must never produce a plan that discloses the query to a third-party provider.

A caller may supply a `QueryDisclosureBudget` that caps distinct third-party providers before the plan is returned. Providers over budget are omitted before execution.

### Provider boundary

Provider adapters remain replaceable and declare supported categories and origin. Execution is bounded by configurable concurrency and per-provider timeout controls; outer cancellation propagates to in-flight work; provider failures are isolated; and provider batches may report degraded state and warnings without failing successful sources.

## Not yet implemented

- Producer-authoritative live GoreeCloud Identity and Privacy Shield verifier transport plus target-runtime acceptance for the Index HTTP boundary.
- External search-provider adapters.
- Snippet generation and advanced ranking signals beyond the current deterministic baseline.
- SafeSearch enforcement.
- Private View.
- GoreeCloud Browser integration.
- GoreeCloud AI answer integration.
- Wardveil Security runtime checks.
- GoreeCloud Mesh discovery/events.
- GoreeCloud Manager administration.
- User/admin Glaze UI surfaces.
- Persistent search history or GoreeCloud Sync.
- Production deployment artifacts.

These remain planned and must not be represented as implemented until code and verification evidence exist.

## Search ↔ Index contract boundary

The development candidate defines `goreecloud.search-index.v1` as the first versioned in-process contract model between Search and a future authenticated GoreeCloud Index transport. Search owns query planning, normalization, deduplication, source agreement, and user-facing ranking. Index supplies document candidates and index-specific provenance. The adapter is transport-injected, supports bounded multi-page retrieval, and reports Index degraded state/warnings to the execution layer. It does not establish live connectivity, authentication, authorization, privacy acceptance, or production runtime integration.

## Index-originated delegation boundary

A future request originating from GoreeCloud Index must use the dedicated cycle-safe contract `goreecloud.search-index-delegation.v1`.

That path is fixed to `external_only` planning. It cannot accept a caller-selected source mode, cannot execute a `GOREECLOUD_INDEX`, `GOREECLOUD_SERVICE`, or `LOCAL` provider, and cannot create a fallback stage. If no approved external provider remains after source filters and the third-party disclosure budget are applied, planning fails before dispatch.

The ordinary Search user/service path may still use `index_first` or other source modes. The dedicated Index-originated path exists specifically to prevent recursive `Index → Search → Index` execution.

The candidate now includes a server-side HTTP source boundary for this contract: `/api/v1/status`, `/api/v1/search`, `/healthz`, and `/readyz`. Query execution requires a verified `goreecloud-index` Identity requester and a consumed opaque Privacy Shield capability reference with exact expected claims. The capability is explicitly not production accepted, and no concrete authority-service client, approved live external provider, reverse proxy, deployment, or production runtime acceptance is introduced.

## Ranking boundary

The current ranker uses transparent deterministic signals derived from parsed query and normalized result evidence: quoted-phrase matches, title/snippet term matches, explicit site/filetype/language matches, and a bounded source-agreement bonus. GoreeCloud Index presence is exposed as provenance with zero ranking weight. Provider rank, click history, advertising payment, cross-query profiles, and hidden behavioral signals are not used.

## Provider execution boundary

The execution engine consumes an already-approved `SourcePlan`. It may not add providers or bypass source-mode privacy restrictions. Per-provider timeout/error states are isolated and reported as explicit attempts. Index-first fallback providers execute only when the primary stage returns fewer raw candidates than the requested target. If all executed providers fail, the result is `unavailable`; partial failures yield `degraded`. Caller cancellation propagates and cancels in-flight provider work.

## Query-disclosure budget boundary

A `QueryDisclosureBudget` may set `max_third_party_providers` to a non-negative integer or leave it unlimited. Budget selection is deterministic because eligible providers are already sorted by configured priority and name. The budget only removes third-party-disclosing providers; it never adds providers or relaxes source-mode/category/source-filter restrictions. Source plans expose the selected third-party-provider count, the applied budget, and how many otherwise eligible providers were omitted. If a zero budget leaves no valid provider for an External Only request, planning fails rather than disclosing the query.
