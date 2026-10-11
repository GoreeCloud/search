# GoreeCloud Search

Privacy-focused, configurable federated search rebuilt from the SearXNG source engine toward GoreeCloud platform standards.

**Lifecycle:** Development only. **Upstream:** SearXNG `f4822b3`. **Glaze:** V1.7 / 1.7.0 inherited foundation, partial mapping (not formally accepted).

## Working implementation

The codebase includes SearXNG's federated engine adapters, categorized web/image/video/news discovery, result aggregation, preferences, HTML search, and machine-readable JSON search (enabled by the provided private profile). GoreeCloud additions include the first semantic Glaze interface layer, a local-only privacy configuration, and a source/contract validation gate. No independent Index, AI answers, local business knowledge, or alert system is implied.

## Develop locally

Follow [upstream SearXNG development instructions](docs/dev/index.rst) to install dependencies. Set a unique 32+-character secret in a local secret store, and launch through the fail-closed wrapper:

```sh
export SEARXNG_SECRET="<unique-strong-secret-from-your-secret-store>"
./scripts/run-private.sh
```

Never use the upstream placeholder key. The profile binds **127.0.0.1**, disables metrics and remote autocomplete, proxies images, defaults to POST, and exposes opt-in JSON on a private interface. Tor-dependent Ahmia and Torch engines are excluded from this standard local profile (they require separate Tor capability and acceptance). It does **not** implement public rate limiting. Internet exposure requires a separate gated HTTPS/reverse-proxy, Valkey limiter, hardened secrets, security/privacy and operational acceptance.

## Private search disclosure safeguards

The local profile now rejects query-bearing GET requests, preserves POST even on Android/WebKit, and disables caching for private search pages. Query-length and distinct-provider limits are set to 512 characters and 32 engines respectively; searches exceeding these limits return 413/422 rather than silently expanding disclosure. Private result pages omit query-bearing RSS/share URL metadata, and the private homepage does not advertise OpenSearch GET-query registration; the private server also returns uncached 404 responses for direct OpenSearch and autocomplete endpoints until an appropriately safe browser integration is qualified. The privacy-sensitive preferences for POST transport, title disclosure, autocomplete, favicons, and image proxy are locked against cookie and request overrides. The private profile also rejects external-bang redirects and first-result (double exclamation mark) navigation before dispatch; unexpected provider/plugin redirects are refused instead of navigating the browser to a third-party site. Query length is validated on the submitted value before operator parsing. Ordinary provider/category bangs remain supported. Shared serialized-preference GET/POST imports are rejected before parsing because upstream can otherwise change selected providers by following a URL; regular local Preferences forms remain available. Primary HTML/JSON search result links are restricted to well-formed HTTP(S) addresses. These safeguards do not cover all embedded or secondary URLs, cannot prevent configured upstream providers from receiving queries, and do not establish anonymity or production security acceptance.

## Search experience

Results display separate selected-source and represented-source summaries: selected engines show which upstream choices were made, while per-engine counts show source labels attached to the safe web results actually displayed. A result aggregated from two engines can contribute to both counts; neither list confirms network contact, authenticates upstream providers, or proves every engine responded. The loopback JSON extension exposes the same represented-source counts. The search header uses GoreeCloud branding, with accessible search labels and responsive Glaze styling. An empty search provides local preference guidance instead of sending users to another service. Privacy policy refusals now have an accessible recovery screen that never reflects query text; local JSON callers receive a structured policy error. These interfaces are source- and Flask-render validated but still need browser, screen-reader, and visual acceptance.

## Local readiness diagnostics

The loopback-only Development profile exposes `GET /readyz`. It returns `200 READY` only when at least one configured, enabled provider processor registered at startup; otherwise it returns `503 NOT_READY`. It reports no provider names or user data. The original `/healthz` liveness route remains unchanged. Readiness is an **in-process startup check**, not proof that any external search provider is reachable, authorized, safe or responding. It is hidden (404) when the private profile is disabled; public operations require a separately authenticated and reviewed health contract.

## Development validation

With SearXNG's pinned requirements installed (including the Python 3.10 compatibility backport when applicable), run the commands below. GitHub source/runtime CI now checks both Python 3.10 and 3.12, while the Chrome browser job uses Python 3.12:

```sh
python -m compileall -q searx
python -m unittest discover -s tests/goreecloud -v
python -m pip install nose2==0.16.0 aiounittest==1.5.0 parameterized==0.9.0 mock==5.2.0
export SEARXNG_SECRET="$(python -c 'import secrets;print(secrets.token_hex(32))')"
python -m nose2 -s tests/unit test_query test_webadapter test_settings_loader test_webapp -v
```

The 2026-10-11 local verification passed 46 GoreeCloud foundation/privacy/Flask-runtime tests and 72 upstream SearXNG query, routing, settings and webapp regressions (118 tests total, in separate isolated runs). The Flask homepage and three local CSS/privacy assets returned HTTP 200. Synthetic browser CI now covers mobile POST results, no query-bearing URL/title, source disclosure, empty-result recovery, error screens and responsive desktop/phone rendering; it does not make any provider-network requests. No live provider searches, device/browser acceptance, full upstream regression suite, or production security acceptance have been verified. This local environment still reports SQLite threading warnings; Ahmia and Torch no longer enter the supplied local engine registry because they require a separately qualified Tor setup. Actual upstream provider availability remains unverified.

## Source boundaries

- [SearXNG provenance and AGPL obligations](UPSTREAM.md)
- [Partial Glaze implementation and acceptance gaps](GLAZE-INTEGRATION.md)
- [Capability roadmap](docs/goreecloud/ROADMAP.md)
- [Local JSON source-selection extension](docs/goreecloud/LOCAL-JSON-API.md)
- [Upstream SearXNG documentation](README.rst)

Pre-reset GoreeCloud Search code persists on historic branches; this import does not automatically provide or authorize GoreeCloud Index, Identity, Privacy Shield, Wardveil Security, or Everkeep integration.
