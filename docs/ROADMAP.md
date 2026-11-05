# GoreeCloud Search — New Product Roadmap

## P0: Original application foundation — under active review
- A clean implementation from the untouched public `main` stub, with no imported historical source.
- Offline-only local-index search; safe POST JSON API; restricted web UI; documented privacy boundaries.
- Original GC UI-based light/dark interface; keyboard and responsive structure.
- Offline tests and reproducible CI; no deployment.

## P1: Search that genuinely spans the web
- Build a reviewed provider/connector interface from scratch. Document which queries and metadata leave GoreeCloud.
- Explicit user-controlled provider selection and outbound search opt-in; per-provider tests, rate limits and timeouts.
- Web results with source attribution, URL normalization, deduplication, partial failures, empty and loading views.
- Strong privacy and abuse controls; threat model; secure configuration; authenticated access before any remote exposure.

## P2: Multiple categories and connected experiences
- Images, videos, news, research, developer resources and local documents via independently reviewed adapters.
- Filters, preferences, locale, accessibility, search relevance and source-specific disclosures.
- Versioned authenticated developer API, native OS clients where justified and verified, and Open Chat integration with least privilege.

## P3: Advanced intelligence and qualified release
- Optional cited AI summaries with strong prompt-injection and privacy isolation.
- Observability and operational controls without sensitive query logging; reliable backups and recovery.
- Approved private staging, cross-browser/OS tests, packaging, deployment and rollback acceptance.

**Explicit non-goals:** Source recovery; SearXNG incorporation; historical Search implementation migration; silently inherited deployments or credentials; premature Stable/Seal claim.

Each milestone moves from proposed → source-present → locally tested → CI tested → privately staged → released only on direct evidence.
