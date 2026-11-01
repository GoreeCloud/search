# GoreeCloud Search — Connector status

**Stage:** First-party opt-in API/UI integration committed to draft PR #2, not merged or deployed.

The original local SQLite FTS5 index remains the default and requires no third-party query disclosure. The first-party POST `/api/search` endpoint now accepts an optional `providers` selection and `share_query: true` consent, and GET `/api/providers` reports runtime availability. The browser UI exposes source selection, disclosure and a per-query consent checkbox. A local-only request never invokes federation.

| Provider | Implementation | Activation and limitations |
| --- | --- | --- |
| Local SQLite FTS5 | First-party index and API | Enabled by default; curated records only, not broad web crawling |
| Brave Search API | Original HTTPS adapter, normalized results | Disabled unless `GC_SEARCH_EXTERNAL_ENABLED=1` and a valid `GC_SEARCH_BRAVE_API_KEY` are configured; explicit per-query consent required; plan/billing and live integration unverified |
| SearXNG | Original loopback HTTP adapter to a *separately operated* service | Disabled unless `GC_SEARCH_EXTERNAL_ENABLED=1` and a validated `GC_SEARCH_SEARXNG_PORT` are configured; the instance must enable JSON responses; instance may forward queries to other engines |

No historical SearXNG code, search database, credential, UI or deployment is incorporated. The new GoreeCloud Search application remains independent.

## Security and usability boundaries

- HTTP listener binds strictly to `127.0.0.1`; no authentication or external exposure is implemented.
- Exact `Host` header matching rejects DNS-rebinding requests; POST rejects foreign `Origin` and `Sec-Fetch-Site` signals before processing the body.
- Invalid request framing or disallowed early requests cause connection closure to avoid unread-body HTTP/1.1 reuse.
- Provider IDs, configuration, result counts and response sizes are bounded; Brave destination and localhost SearXNG destination are fixed by code; provider redirects are not followed; credentials remain server-side.
- Explicit per-query consent and global enablement are both required. The UI resets consent after each search or provider switch and disables source changes during active requests.
- External sources receive the search terms when explicitly used; Brave may incur charges and SearXNG may forward queries upstream. Results carry provider attribution and failures are represented by bounded warnings, not raw error details.
- The Brave in-process rate gate is a safeguard, **not** a durable paid-usage budget. Do not activate on a billable plan without explicit owner-approved quotas/usage monitoring.

## Verification and release gates

Offline unit, HTTP, and static UI contract tests plus a no-skip CI gate are committed. This does **not** establish live API compatibility, real-browser accessibility, native OS acceptance, secure remote hosting, operational rate limits or production deployment. GitHub CI at the final commit must pass before accepting this integration. PR #2 must remain draft and unmerged for review.

Reference: `docs/OPTIONAL_PROVIDER_SECURITY_REVIEW.md`; `docs/THIRD_PARTY_AUDIT.md` if present; current `tests/test_optional_providers.py` and `tests/test_http_integration.py`.
