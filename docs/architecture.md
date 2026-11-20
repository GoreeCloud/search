# GoreeCloud Search architecture

This is an independent search-index development prototype. No commercial
metasearch API is in its critical request path.

## Components and ownership

- Operator seed registration: PostgreSQL crawl_frontier, crawl_host_limits,
  crawl_exclusions tables, implemented in goree_search/frontier.py.
- Host-safe claim: PostgreSQL host-row locks and SKIP LOCKED allow only one
  leased page per host per scheduler pass, with shared inter-claim cooldown.
- Network layer: HTTPS CONNECT proxy listens only on loopback, resolves all
  DNS addresses, refuses any non-global address and connects to the selected
  validated IP. Scrapy performs hostname-based end-to-end TLS.
- Robots preflight: fetch robots.txt through the same restricted HTTPS proxy.
  Unknown/oversized/5xx/redirect responses prevent page fetch; explicit
  disallow stops crawling and purges old indexed results. Scrapy independently
  checks robots rules during actual requests.
- Crawling: Scrapy workers, fixed size and time limits, no automatic
  redirects, per-domain delay, optional single-seed mode.
- Parsing: Trafilatura extracts HTML, yielding URL, title, body and hash.
- Discovery: links on allowed HTTPS hosts enqueue into the SQL frontier; they
  are not immediately downloaded, ensuring every crawl goes through claims.
- Index: OpenSearch lexical fields, deterministic URL hash IDs. A noindex or
  non-HTML/non-200 response generates a deletion item.
- Serving: FastAPI GET /v1/search, GET /v1/health; Next.js web search form
  renders HTML-escaped result text without visitor accounts.

## Lifecycle

Claimed URLs hold a 20-minute lease. Successful fetches are next due after
seven days. An abandoned lease becomes claimable after expiry; retries use
bounded backoff and eventually fail closed after repeated attempts. Explicit
operator exclusions prevent enqueue and are checked by the indexing pipeline.

## Consistency limitations

An exclusion and an OpenSearch deletion occur in separate systems, not in a
single atomic transaction. Stop all workers before a removal, purge the index,
verify search-visible absence, and only then restart. Future work should add
outbox-backed delete reconciliation and verified owner intake.

A crawler-specific proxy is not a process/host firewall. Production hosts must
independently deny internal and metadata network destinations. Robots-fetch
failure behavior and large-site policy acceptance require additional tests.

Not implemented: sitemap import, PDF parsing, WARC archival, distributed link
ranking, semantic retrieval, full-web crawl, or an installed daemon.
