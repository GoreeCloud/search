# GoreeCloud Search — Connector status

**Stage:** First-party opt-in API/UI integration committed to draft PR #2, not merged or deployed.

The original local SQLite FTS5 index remains the default and requires no third-party query disclosure. The first-party POST `/api/search` endpoint now accepts an optional `providers` selection and `share_query: true` consent, and GET `/api/providers` reports runtime availability. The browser UI exposes source selection, disclosure and a per-query consent checkbox. A local-only request never invokes federation.

| Provider | Implementation | Activation and limitations |
| --- | --- | --- |
| Local SQLite FTS5 | First-party index and API | Enabled by default; curated records only, not broad web crawling |
| Brave Search API | Original HTTPS adapter, normalized results | Disabled unless `GC_SEARCH_EXTERNAL_ENABLED=1`, a valid `GC_SEARCH_BRAVE_API_KEY`, and an explicit positive `GC_SEARCH_BRAVE_DAILY_CAP` are configured; owner-private SQLite reservation and per-query consent required; real plan/billing and live compatibility still unverified |
| SearXNG | Original loopback HTTP adapter to a *separately operated* service | Disabled unless `GC_SEARCH_EXTERNAL_ENABLED=1` and a validated `GC_SEARCH_SEARXNG_PORT` are configured; the instance must enable JSON responses; instance may forward queries to other engines |

No historical SearXNG code, search database, credential, UI or deployment is incorporated. The new GoreeCloud Search application remains independent.

## Security and usability boundaries

- HTTP listener binds strictly to `127.0.0.1`; no authentication or external exposure is implemented.
- Exact `Host` header matching rejects DNS-rebinding requests; POST rejects foreign `Origin` and `Sec-Fetch-Site` signals before processing the body.
- Invalid request framing or disallowed early requests cause connection closure to avoid unread-body HTTP/1.1 reuse.
- Provider IDs, configuration, result counts and response sizes are bounded; Brave destination and localhost SearXNG destination are fixed by code; provider redirects are not followed; credentials remain server-side.
- Explicit per-query consent and global enablement are both required. The UI resets consent after each search or provider switch and disables source changes during active requests.
- External sources receive the search terms when explicitly used; Brave may incur charges and SearXNG may forward queries upstream. Results carry provider attribution and failures are represented by bounded warnings, not raw error details.
- Brave now also uses a **durable local SQLite per-UTC-day request ceiling** that fails closed before API egress. This protects a single ledger across process restarts and cooperating processes, but **does not enforce a monetary, provider-account or multi-device billing limit**. Do not activate on a paid plan without account-level provider caps, verified terms, owner-approved quotas and usage monitoring. See [paid usage controls](PAID_USAGE_CONTROLS.md).

## Verification and release gates

Offline unit, HTTP, and static UI contract tests plus a no-skip CI gate are committed. This does **not** establish live API compatibility, real-browser accessibility, native OS acceptance, secure remote hosting, operational rate limits or production deployment. GitHub CI at the final commit must pass before accepting this integration. PR #2 must remain draft and unmerged for review.

Reference: `docs/OPTIONAL_PROVIDER_SECURITY_REVIEW.md`; `docs/THIRD_PARTY_AUDIT.md` if present; current `tests/test_optional_providers.py` and `tests/test_http_integration.py`.
