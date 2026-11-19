# Architecture — GoreeCloud Search alpha

Source and status: this is a development implementation and not a deployed or
production accepted search engine. The independent crawl and index are owned by
GoreeCloud. Scrapy, Trafilatura and OpenSearch are reused as external components.

## Flows

1. Operator runs a curated public-URL seed import to PostgreSQL.
2. The CLI claims eligible URLs using FOR UPDATE SKIP LOCKED and leases.
3. The Scrapy spider uses robots.txt, a per-domain delay, bounded traversal and
   allowlisted host validation for every request and redirect.
4. Trafilatura extracts indexable HTML into a deterministic document schema.
5. The index pipeline writes documents to OpenSearch by SHA-256 URL key and
   completes the PostgreSQL frontier record. Failed writes are requeued.
6. FastAPI performs BM25 multi_match ranking against the independent index.
7. Next.js server-renders search responses with escaped text and safe external links.

Components currently in repository:
- goree_search/security.py — URL policy / network preflight
- goree_search/frontier.py — queued, leased, fetched, excluded and failed states
- goree_search/crawler.py — robots-aware per-domain crawl
- goree_search/extraction.py — HTML extraction / noindex evaluation
- goree_search/indexing.py — OpenSearch mapping / search
- goree_search/api.py — public read-only API
- apps/web — independent responsive search frontend

## Known gaps and next gates

- Egress controls or pinned DNS resolution are required before unrestricted
  crawling; current hostname DNS validation alone is not resistant to DNS rebinding.
- PostgreSQL frontier crash/recovery and distributed timing need integration tests.
- Site-owner verified removal, recrawl, tombstones and deletion propagation are not
  yet implemented. Do not crawl at scale while these gates are open.
- Do not conflate search snippets with an auditable content archive. WARC,
  sitemap ingestion, PDF/Tika, language-specific analyzers and authority reranking
  are planned, not built.
- Next.js dependency lockfile and production CSP / reverse proxy rules need acceptance.
- OpenSearch alpha mapping uses one shard and no replicas for local development.
  Scaling and snapshots require workload-specific design.
- GoreeShield privacy, Wardveil security, GoreeCloud Mesh integration and
  GoreeCloud Identity administration have distinct responsibilities.
  GC UI tokens are carried from the approved alpha, not a claim of consumer Stable.
