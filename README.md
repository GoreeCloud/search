# GoreeCloud Search

A **development-stage, independent public-web search engine**: first-party
crawl scheduling, retrieval API and web UX, using separately licensed
Scrapy, Trafilatura, PostgreSQL, OpenSearch, FastAPI and Next.js.

**Status:** 0.1.0-alpha source preview. Not Stable, not production deployed,
not a full-web-scale index. Source is not a SearXNG fork or metasearch proxy.
The historical GitHub secret scanning alert requires separate verification
before restoring old source.

## What currently works in source

- Public-web HTTP(S) URL normalization and allowlist checks.
- PostgreSQL lease-based crawl frontier and idempotent seed registration.
- Scrapy crawler with robots.txt obedience, conservative politeness,
  bounded depth/page counts and same-host hyperlink discovery.
- Trafilatura HTML text extraction, X-Robots-Tag/meta robots noindex exclusion.
- OpenSearch document ingestion and independent BM25-style lexical search.
- FastAPI GET /v1/search and /v1/health, plus responsive Next.js search UI.
- Python API/security/extraction/indexing tests and GitHub CI source workflows.

No external commercial search API is used to return results. Current source
does **not** implement: Google-like comprehensive web coverage, WARC archives,
PDF extraction, semantic reranking, PageRank, suggestion API, owner removals,
multi-host distribution, production secure administration or deployment.

## Local developer setup (not a production deployment)

Requires Python 3.11+, Node 22+, Docker Compose (development compatibility
only) and a disposable machine with at least several GiB of free RAM. Review
[security restrictions](docs/security.md) before enabling any external network
crawler requests. Do **not** run the crawler on an unrestricted trusted network.

1. From the repository root, start isolated **development-only** backing services:

       docker compose -f compose.dev.yaml up -d

2. Install the Python package into a virtual environment:

       python3 -m venv .venv
       . .venv/bin/activate
       python -m pip install -e ".[test]"

3. Set the values in .env.example in your development shell (the app does not
   automatically load .env files). Then initialize and seed selected PUBLIC
   sites; always review robots policies and obtain appropriate permission:

       export DATABASE_URL=postgresql://goree_search:local_dev_only_change_me@127.0.0.1:5432/goree_search
       export OPENSEARCH_URL=http://127.0.0.1:9200
       goree-search init
       goree-search seed https://www.python.org/
       goree-search crawl --claim 10 --max-pages 50

4. Start the private-loopback API, deliberately without access logs:

       uvicorn goree_search.api:app --host 127.0.0.1 --port 8000 --no-access-log

5. Separately start the web frontend:

       cd apps/web
       npm install
       npm run dev

6. Visit http://localhost:3000 to search **only** pages indexed by this crawl.

To run a one-off crawl without PostgreSQL frontier, use:

    goree-search crawl --url https://www.python.org/ --max-pages 30

The OpenSearch and PostgreSQL credentials in compose.dev.yaml are **intentionally
insecure local development examples**. All exposed ports bind to 127.0.0.1.
Do not copy into VPS, reverse proxy, or public deployment configurations.

## Tests

    python -m pip install -e ".[test]"
    python -m pytest -q
    python -m compileall -q goree_search
    cd apps/web && npm install && npm run typecheck && npm run build

GitHub Actions runs both groups automatically on reviewable PRs. The web dependency tree is locked with package-lock.json; transitive security
and reproducibility reviews remain production acceptance gates. Runtime, DNS/egress, crawl
integration and restoration checks remain release blockers.

## Governance and platform integration

- GoreeShield: minimizes query collection and defines privacy retention.
- Wardveil: crawler threat model, security controls and response.
- GoreeCloud Mesh: future opt-in API interoperability, not a deployed connector.
- GoreeCloud UI: approved alpha semantic tokens and accessible interaction.
- GoreeCloud Identity: future authenticated administration, not public search login.

GoreeCloud Index is the distinct **local desktop search** product; this
repository targets the **public web**. See [architecture](docs/architecture.md)
and [security/privacy](docs/security.md).

## License and origin

Original GoreeCloud source in this repository: [MIT](LICENSE), copyright 2026
GoreeCloud. The upstream frameworks, libraries, engines and token sources
retain their respective copyright and license terms;
see [third-party notices](THIRD_PARTY_NOTICES.md).
