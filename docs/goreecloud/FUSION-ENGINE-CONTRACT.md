# GoreeCloud Search Fusion Engine — offline foundation and integration contract

**Stage:** Development-only experimental source on the GoreeCloud Search
development branch. **Not** connected to the deployed website, live external
providers, the native Linux `.pyz`, or a public API.

`native_search/fusion.py` contains the first independent GoreeCloud-owned
result-fusion primitive. It accepts immutable `SourceResult` cards for
`web`, `images`, `videos` and `news`, and emits `FusedResult` objects. Its
standard-library implementation performs no I/O or background requests.

`native_search/dispatch.py` adds the **Development-only adapter-dispatch
contract**. It accepts a bounded query and a finite set of named asynchronous
provider adapters, checks their explicit per-category `ProviderRights`, runs
only admitted adapters with cooperative deadlines and a maximum concurrency
limit, and combines their normalized cards through the existing ranker. It
returns a versioned `FusionResponse` with one fused result list and
query-free per-provider health states (`blocked`, `ok`, `empty`, `timeout`,
`failed`). It neither ships provider adapters nor authorizes provider use.

## v1 offline dispatcher boundaries

- Rights default to **deny**. Fetch, fusion and display must each be explicitly
  allowed and accompanied by a nonempty reference to reviewed upstream terms;
  category membership is also explicit. `rights_basis` defaults to `unverified`
  and cannot admit. `synthetic_fixture` admits only with the explicit
  `allow_synthetic_fixtures=True` testing switch, **off by default**;
  `contract_reviewed` is an operator assertion requiring independent
  documentary confirmation before configuration. No shipped provider has this
  assertion. A code flag is not independent legal permission, nor is a
  synthetic fixture rights grant permission for Google, Bing, Brave, or any
  other real upstream.
- Up to eight named providers may be registered; each can return at most 40
  `SourceResult` cards, with at most four concurrent calls. A source receives
  the query only if admitted; inaccessible or denied sources are not called.
- The default cooperative per-provider deadline is three seconds (maximum
  ten). Real adapters **must** be asynchronous, honor cancellation, enforce
  their own socket/client deadline, upstream rate budget and egress policy,
  and never spawn unbounded blocking work. This module is not a process-level
  kill switch for a malicious or stuck third-party connector.
- Invalid adapter shape, mixed source identity and invalid ranks fail that
  **one provider** without sacrificing another admitted provider's result.
  Source errors are counted, not logged or reflected with query-bearing
  exception messages; no hidden retries, substitute providers or user-query
  cache are implemented.
- `FusionResponse` has `schema_version=1`, `category`, a unified `results`
  tuple, source `providers` outcome tuples, and overall `status` (`ok`,
  `partial`, `empty`, `unavailable`). `partial` covers degraded or blocked
  configured providers; `empty` indicates permitted sources responded but
  produced no publishable results. This is a Python data contract, **not** an
  exposed JSON route or a promise of user-facing production behavior.
- Inputs and test fixtures are synthetic and offline. The currently deployed
  SearXNG-derived Development site, packaged Linux `.pyz`, Caddy ingress,
  public host and source provider configuration are unchanged.

## v0 deterministic behavior

- Every card records a validated lowercase source identifier, category,
  one-based position, HTTP(S) destination, title and optional description or
  image media URL; invalid destinations/cards are discarded. Category mismatch,
  malformed source identity, invalid rank or oversized input fails closed.
- Web, News and Videos use conservative destination URL equality, stripping
  fragments, default ports and listed tracking parameters. Semantic query
  parameters are preserved. This does **not** collapse syndication copies,
  mirrored hosts, video URL aliases or articles about the same event.
- Images deduplicate by a validated original/media URL, never just the page
  hosting the asset. Images without media identity remain separate until
  richer evidence exists. Perceptual hashing is not implemented.
- A duplicate receives at most one vote per distinct source; if a single
  source returns that URL more than once, its best position wins. A score
  sums `1 / (60 + position)` across its source votes (reciprocal rank
  fusion). Stable encounter order breaks exact-score ties.
- Source/rank evidence is internal to the model, not a provider-selection
  requirement in the product UI. Exposing or hiding attribution is subject
  to each approved provider agreement.
- Inputs are bounded to 1,000 cards, output to 100; no user query, response,
  logging, HTTP handler, SQLite table, cache or provider SDK is involved.
  Title (512 characters), description (2,000) and URL (4,096) fields are
  separately bounded before inclusion.

## Integration acceptance still required

1. **License gate:** Only explicit, source-specific allowed usages can reach
   a provider adapter or populate the production fuse input. A *technically
   accessible* upstream HTML page is not contractual permission. Brave's
   derivative/caching restrictions and Google/Bing API lifecycle changes must
   be resolved before their native fusion activation.
2. **Adapter contract:** Map provider-specific payloads into typed vertical
   cards, validate redirects/media and language/locale, enforce per-provider
   limits, budget, timeout, network egress and content rights. Partial
   failures must not be disguised as an empty index.
3. **Orchestrator:** The offline cooperative dispatch contract exists, but it
   still needs a deployment-qualified async transport, signed and reviewed
   source-rights configuration, cross-request worker/request budget, upstream
   rate-limit/backoff policy and cancellation under real outages. Keep no
   invisible fallback source, expose degraded-state telemetry without raw user
   queries, and explain privacy implications of automatic provider fanout.
   Prefer POST for private Search to avoid query URLs.
4. **Ranking acceptance:** Compare fused results against a pinned synthetic
   and (separately authorized) real relevance corpus. Add query relevance,
   recency, quality/spam, domain diversity, language and visual/media
   similarity signals only after correctness and benchmark evidence.
5. **Runtime:** Integrate through a new versioned GoreeCloud-owned boundary
   rather than calling this helper a fully independent search service.
   Provide load, recovery, rate limiting, security, authentication, privacy,
   observability and rollback acceptance on the exact candidate before any
   public or native OS release claim.

Offline tests: `python3 -m unittest discover -s tests/native -p test_fusion.py -v`.
Dispatch tests: `python3 -m unittest discover -s tests/native -p test_dispatch.py -v`.
The existing native Linux service packaging has a fixed three-module
allowlist and does **not** include this file. Expanding that artifact is a
separate security and release change, not an implied result of adding source.
