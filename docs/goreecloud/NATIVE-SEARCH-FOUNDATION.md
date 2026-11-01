# GoreeCloud Search — Native Foundation (Development)

## Status and boundaries

This is an **isolated first implementation**, not a Stable release and **not connected to search-dev.goreecloud.com** by default. Existing SearXNG-backed search and its private VPS deployment remain unchanged. The long-term goal is to own crawling, indexing, ranking, and query delivery while using external providers, if any, only where allowed and explicitly selected.

### Implemented

- SQLite FTS5 persistent index with transactional upsert and deletion, Unicode tokens, quoted MATCH queries, title-weighted BM25 ranking, consistent source URLs, and no provider or analytics calls.
- An allowlisted HTTPS-only, single-process crawler. It checks robots.txt before requesting a page, honors `Disallow`, `Crawl-delay`, HTML `noindex`/`nofollow`, and `X-Robots-Tag`; limits depth, pages, links and response bytes; forbids HTTP, IP literals, private DNS destinations, external hosts, redirects, URL queries and URLs with credentials. TLS connections pin previously checked public IP addresses while validating the original hostname.
- A loopback-only development JSON API, `POST /v1/search`, with bounded query/body/result limits, JSON-only requests, no CORS, no search GET query strings, no request logging, and anti-caching/privacy response headers.
- An explicit CLI for fixture import, local serving, and network crawling. **No default seeds, background jobs, scheduled crawling or public bindings.**

### Offline trial

From the repository root, with Python 3.10+ and SQLite compiled with FTS5:

```sh
python3 -m unittest discover -s tests/native -v
python3 -m native_search import-json --db /tmp/goreecloud-native-search.db --input tests/native/fixtures.json
python3 -m native_search serve --db /tmp/goreecloud-native-search.db --port 8789
# From a second terminal:
curl -sS -X POST http://127.0.0.1:8789/v1/search \
  -H 'Content-Type: application/json' \
  --data '{"query":"native search","limit":5}'
```

For a real, explicitly approved public host:

```sh
python3 -m native_search crawl --db /tmp/goreecloud-native-search.db \
  --allow-network --allow-host PUBLIC_HOSTNAME \
  --seed https://PUBLIC_HOSTNAME/ --max-pages 5 --max-depth 1
```

Takedowns are available through `python3 -m native_search remove-url --db DATABASE --url HTTPS_URL`. The prototype fetcher uses direct, identifiable HTTPS egress rather than the Tor provider relay. No production crawling should be launched with this prototype. Avoid crawling sites until domain permissions, contact information, retention, legal/publisher policy, operations, recrawl budgets, domain-specific safeguards and monitoring are assessed.

### Not yet implemented / release gates

- Publisher outreach, crawl scheduling, efficient frontier, sitemaps, per-host politeness across workers, robots caching expiry, canonical/duplicate cluster, charset/encoding detection, spam/malware controls, content rights and takedowns, incremental refresh, storage scale, backup/restore, ranking relevance evaluation, and multilingual processing.
- Images, Videos and News-specific native extractors, result cards and ingestion; only Web-document text is indexed in this milestone.
- Public or shared access, production rate limiting/authentication, distributed index, sandboxed fetch worker, external search provider integration, cross-device UI integration and reliability acceptance.

**Do not** expose the native API, treat example.org fixture data as internet coverage, or replace SearXNG until it passes separate security, privacy, quality and performance review. This foundation is designed to be replaceable/integrable, not promoted as an independent web search engine today.

### Milestone sequence

1. **Native foundation:** reproducible index, crawler, loopback API and offline tests (this patch).
2. **Private integration spike:** define a read-only native result adapter and an explicit development UI source choice in GoreeCloud UI; isolate its database and requests.
3. **Corpus quality:** approved seed registry, content removal policies, sitemaps, retries, canonical clusters, recrawl planning, malware/spam assessment and relevance benchmarks.
4. **Verticals and scale:** add image/video/news extraction, observability, storage/backup design, infrastructure capacity study, and performance controls.
5. **Promotion candidate:** compare native result availability and relevance against permitted alternatives; complete security/privacy and disaster-recovery acceptance. Only then consider Stable.

Do not remove or bypass the approved provider privacy relay simply because the native prototype can search its own fixtures.
