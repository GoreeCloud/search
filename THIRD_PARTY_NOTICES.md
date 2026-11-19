# Dependencies and attribution

This repository contains newly authored GoreeCloud source, not a vendored copy of
historical search engine code. Dependencies remain the property of their respective
copyright holders, and are installed separately.

| Dependency | Upstream repository | License (review upstream release package) |
| --- | --- | --- |
| Scrapy | https://github.com/scrapy/scrapy | BSD-3-Clause |
| Trafilatura | https://github.com/adbar/trafilatura | Apache-2.0 |
| OpenSearch | https://github.com/opensearch-project/OpenSearch | Apache-2.0 |
| opensearch-py | https://github.com/opensearch-project/opensearch-py | Apache-2.0 |
| FastAPI | https://github.com/fastapi/fastapi | MIT |
| PostgreSQL | https://github.com/postgres/postgres | PostgreSQL License |
| psycopg | https://github.com/psycopg/psycopg | LGPL-3.0, with applicable project exceptions |
| Next.js | https://github.com/vercel/next.js | MIT |
| React | https://github.com/facebook/react | MIT |
| GoreeCloud UI tokens | https://github.com/GoreeCloud/gc-ui | MIT |

Transitive dependencies, container images, release-specific notices and SBOM must be
reviewed before Stable or production distribution. No direct SearXNG source has been
copied from the historical repository. In particular do not restore historical
search source while the November 2026 secret-scanning alert remains unresolved.
