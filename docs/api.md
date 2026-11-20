# Public read-only HTTP API

FastAPI endpoints:

| Endpoint | Meaning |
| --- | --- |
| GET /v1/health | Process health (not an index readiness guarantee) |
| GET /v1/search | Independent lexical OpenSearch retrieval |

Example GET request:

    /v1/search?q=linux%20privacy&limit=10&offset=0

The query must contain 2 to 256 characters. Limit 1 to 30; offset 0 to
1000. An unavailable index returns 503, not fallback results.

Response fields: total, limit, offset, results array. Each result has URL,
host, title, description and score. Example data is not fetched by tests
unless the disposable index-smoke fixture is expressly enabled.

No anonymous admin endpoints, removal HTTP endpoint, account profiles or
commercial-search-provider calls exist. The operator CLI handles exclusions.
Production authentication, rate limits and query logging minimization remain
acceptance requirements.
