# GoreeCloud Search

Independent, privacy-first **public-web search engine alpha**. First-party
scheduling, crawling security, search API and web interface combine with
open-source Scrapy, Trafilatura, PostgreSQL, OpenSearch, FastAPI and Next.js.

**Status:** development-source alpha; not Stable, deployed, or web-scale.
GoreeCloud Index is a separate local desktop search product.

## Implemented

- HTTPS-only operator-reviewed seeds and durable PostgreSQL URL scheduling.
- One leased URL per host and shared host cooldown across workers, with
  exponential failure backoff and timed recrawl eligibility.
- Fail-closed HTTPS robots.txt preflight (network errors and oversized files
  prevent content fetch), plus Scrapy robots-aware crawling and conservative
  fetch limits. Same-host links are queued for later scheduled runs.
- Internal loopback HTTPS CONNECT proxy with DNS answer validation and
  IP-pinned TCP connections to reduce DNS-rebinding exposure. Redirect,
  file/data/FTP and meta-refresh fetching are disabled.
- Trafilatura extraction, duplicate URL IDs and OpenSearch lexical results.
- Deletion from the existing index when an indexed URL becomes noindex or
  receives a non-200 or non-HTML response.
- Operator exclusion tombstone and idempotent indexed-document purge command.
- Public read-only FastAPI and a responsive Next.js search UI using
  GoreeCloud UI alpha semantic colors.
- GitHub CI with PostgreSQL lease tests, disposable OpenSearch lifecycle
  smoke tests, Python tests and Next.js build.

No commercial search provider supplies the results. The corpus is only the
set of pages that the operator has legitimately indexed.

## Local development

Prerequisites: Python 3.11+, Node 22+, npm and Docker Compose.
The following demo credentials and disabled OpenSearch security plugin are
**local development ONLY**. Bindings are loopback only; never expose these
services publicly or deploy this example on an unrestricted trusted network.

    docker compose -f compose.dev.yaml up -d
    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install -e ".[test]"
    export DATABASE_URL=postgresql://goree_search:local_dev_only_change_me@127.0.0.1:5432/goree_search
    export OPENSEARCH_URL=http://127.0.0.1:9200
    goree-search init

Review the site's robots policy and your authorization before seeding. Example:

    goree-search seed https://www.python.org/
    goree-search crawl --claim 1 --host-delay 5 --max-pages 20

Discovered links are queued and require a later invocation. The program does
not create an always-on scheduler, daemon or recurring crawl. A single
operator-selected HTTPS page can be fetched independently with:

    goree-search crawl --url https://www.python.org/ --max-pages 1

Start the read-only API:

    uvicorn goree_search.api:app --host 127.0.0.1 --port 8000 --no-access-log

Start the web interface separately:

    cd apps/web
    npm ci
    npm run dev

Open http://localhost:3000. It searches only already indexed content.

### Operator exclusion / removal

Stop all crawler workers first. Verify the exact destination and authority.

    goree-search remove https://example.org/old --reason "Verified operator request"

The command first stores a permanent PostgreSQL exclusion and then removes
the indexed document with a search-visible refresh. If the index is offline,
retry the same command. Verify the URL is absent before restarting workers.
No public site-owner verification or automatic appeals are implemented.

## Validation

    python -m pip install -e ".[test]"
    python -m compileall -q goree_search tests
    python -m pytest -q
    cd apps/web && npm ci && npm run typecheck && npm run build

PostgreSQL test coverage requires TEST_DATABASE_URL and OpenSearch lifecycle
tests require TEST_OPENSEARCH_URL; CI provisions disposable services. Neither
is proof of safe unrestricted crawling, production recovery or performance.

## Documentation and release boundaries

- [Architecture](docs/architecture.md)
- [Security and privacy](docs/security.md)
- [Operator procedures](docs/operations.md)
- [Public API](docs/api.md)

Production gates: host/network egress firewall, live-site robots policy checks,
verified owner removal workflows, index consistency under concurrent deletion,
production TLS and admin authentication, backups/restores, crawled-site test
fixtures, relevance benchmarks, workload testing, and privacy at all proxy
layers. Full-web indexing, Tika/PDF, WARC, embeddings, PageRank, sitemap import,
distributed operations and native clients remain planned, not implemented.

The mandatory GoreeCloud systems have distinct responsibilities: GoreeShield
privacy; Wardveil cybersecurity; GoreeCloud Mesh integration; GoreeCloud UI
design language; GoreeCloud Identity authorization. Their integration is not
certified or deployed by these source files.

## Open-source origin

Original GoreeCloud source: [MIT](LICENSE), copyright 2026 GoreeCloud.
Third-party frameworks and engines retain their own licenses and notices:
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No historical SearXNG
code was imported, and a reported historical GitHub secret-scanning alert
continues to require independent evidence-based review.
