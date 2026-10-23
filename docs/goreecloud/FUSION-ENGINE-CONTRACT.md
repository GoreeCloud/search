# GoreeCloud Search Fusion Engine — offline foundation and integration contract

**Stage:** Development-only experimental source on the GoreeCloud Search
development branch. **Not** connected to the deployed website, live external
providers, the native Linux `.pyz`, or a public API.

`native_search/fusion.py` contains the first independent GoreeCloud-owned
result-fusion primitive. It accepts immutable `SourceResult` cards for
`web`, `images`, `videos` and `news`, and emits `FusedResult` objects. Its
standard-library implementation performs no I/O or background requests.

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
3. **Orchestrator:** Parallel dispatch with bounded deadlines and cancellation,
   no invisible fallback source, explicit degraded-state telemetry without
   raw user queries, and clear privacy consent/disclosure for automatic
   provider fanout. Prefer POST for private Search to avoid query URLs.
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
The existing native Linux service packaging has a fixed three-module
allowlist and does **not** include this file. Expanding that artifact is a
separate security and release change, not an implied result of adding source.
