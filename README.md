# GoreeCloud Search

Privacy-focused, configurable federated search rebuilt from the SearXNG source engine toward GoreeCloud platform standards.

**Lifecycle:** Development only. **Upstream:** SearXNG `f4822b3`. **Glaze:** V1.7 / 1.7.0 inherited foundation, partial mapping (not formally accepted).

## Working implementation

The codebase retains upstream SearXNG source adapters, but the GoreeCloud private product exposes **exactly two built-in web-search providers: Brave Search (the search service associated with Brave Browser) and Startpage**. All other adapters, including Brave API and specialized Brave or Startpage category variants, are excluded from the active registry. Both are enabled by default, and users can narrow a query to either. The private homepage also has Brave-only and Startpage-only quick-search buttons; the normal Search button continues to honor saved source preferences. HTML and private JSON search remain available. GoreeCloud additions include the first semantic Glaze interface layer, a local-only privacy configuration, and a source/contract validation gate. No independent Index, AI answers, local business knowledge, or alert system is implied.

## Owner-approved homepage design

The official October 11, 2026 desktop/mobile mockups define GoreeCloud Search's frontend: cyan search-mark and navy/cobalt GoreeCloud wordmark, centered white search box, concise privacy principles, prominent blue search button, responsive header, moon appearance toggle and restrained footer. The visual specification and scope are documented in [Official homepage](docs/goreecloud/OFFICIAL-HOMEPAGE.md). The layout is implemented against the actual private Development app—not as a disconnected static demo—and retains the POST search, no-network source preview and strict Brave Search/Startpage policy. Privacy slogans are design principles, not proof that upstream providers do not track visitors.

## Develop locally

Follow [upstream SearXNG development instructions](docs/dev/index.rst) to install dependencies. Set a unique 32+-character secret in a local secret store, and launch through the fail-closed wrapper:

```sh
export SEARXNG_SECRET="<unique-strong-secret-from-your-secret-store>"
./scripts/run-private.sh
```

Never use the upstream placeholder key. The profile binds **127.0.0.1**, disables metrics and remote autocomplete, proxies images, defaults to POST, and exposes opt-in JSON on a private interface. No other upstream engine is registered as an available search option. Startpage has an upstream proof-of-work anti-bot challenge, so inclusion and enabled state do **not** establish that real Startpage searches work. It does **not** implement public rate limiting. Internet exposure requires a separate gated HTTPS/reverse-proxy, Valkey limiter, hardened secrets, security/privacy and operational acceptance.

## Private search disclosure safeguards

The local profile now rejects query-bearing GET requests, preserves POST even on Android/WebKit, and disables caching for private search pages. It also refuses non-loopback Host headers and browser cross-origin/cross-site form submissions before any search dispatch (a limited DNS-rebinding/CSRF defense), and caps search/preview form bodies at 64 KiB. Local non-browser clients can omit Origin headers; this is not a substitute for public authentication or abuse prevention. Query-length and distinct-provider limits are set to 512 characters and **two engines** respectively; searches exceeding these limits return 413/422 rather than silently expanding disclosure. Private result pages omit query-bearing RSS/share URL metadata, and the private homepage does not advertise OpenSearch GET-query registration; the private server also returns uncached 404 responses for direct OpenSearch and autocomplete endpoints until an appropriately safe browser integration is qualified. The privacy-sensitive preferences for POST transport, title disclosure, autocomplete, favicons, and image proxy are locked against cookie and request overrides. The private profile also rejects external-bang redirects and first-result (double exclamation mark) navigation before dispatch; unexpected provider/plugin redirects are refused instead of navigating the browser to a third-party site. Query length is validated on the submitted value before operator parsing. Only the Brave Search (`!br` or `!brave`) and Startpage (`!sp` or `!startpage`) source bangs, and general/web category bangs, are accepted. Unknown or third-party bangs are rejected rather than silently falling back; unsupported providers cannot be selected or dispatched. Shared serialized-preference GET/POST imports are rejected before parsing because upstream can otherwise change selected providers by following a URL; regular local Preferences forms remain available. Primary HTML/JSON search result links are restricted to well-formed HTTP(S) addresses, rejecting malformed or zero ports and invisible Unicode control characters. These safeguards do not cover all embedded or secondary URLs, cannot prevent configured upstream providers from receiving queries, and do not establish anonymity or production security acceptance.

## Search preview (no provider requests)

On the private homepage and result pages, **Preview sources without searching** parses the submitted query and local preferences and shows selected provider names, categories, language and safe-search level without creating a provider search executor. Users can then explicitly continue with the selected sources, or opt to search only one selected provider. On normal results pages, each selected source also has a **Search only** POST action, plus a direct **Both sources / Brave Search / Startpage** switch. These controls change the current query's provider selection without changing browser preferences or exposing search terms in the URL. The selected provider(s) remain scoped across search-header resubmission and next/previous/numbered pagination. Query bangs are removed only for the dedicated switch forms so users can switch from `!br` to Startpage without silently staying on Brave. Preview and its continuation use POST without query-bearing URLs and inherit the private 512-character and two-source limits. Preflight validates policy but cannot guarantee a provider is reachable, will receive a request, or will protect query privacy. It must not be mistaken for consent or production authorization.

When Startpage is among the selected sources, the HTML preview also warns about its unverified anti-bot proof-of-work behavior and confirms no substitute provider is used. Search can be focused with `/` from non-editable page content without triggering network requests or interfering with slash typed inside a search input.

The same private local preflight is available through `POST /preview` with `q` and `format=json` in the **body**; its response includes only query length, selected engines/categories and explicit `network_requests_made: false`, not raw query terms. GET to this endpoint is rejected and uncached; the route is unavailable outside the local private profile. The API is not authenticated and must remain loopback-only.

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

On October 16, 2026, the development laptop baseline at `90ad0cd` passed **101 GoreeCloud tests and 72 upstream regressions (173 tests total)** using isolated Python 3.10 dependencies; source compilation also passed. The request-boundary hardening candidate subsequently passed **105 GoreeCloud tests** and Python compilation on the same isolated laptop environment; upstream regressions and exact-head CI must be rerun for final validation. The previously accepted exact-commit GitHub CI at `90ad0cd` passed the repository's Python 3.10/3.12 checks and browser smoke. The Flask homepage and three local CSS/privacy assets returned HTTP 200. Synthetic browser CI now covers mobile POST results, no query-bearing URL/title, source disclosure, empty-result recovery, error screens and responsive desktop/phone rendering; it does not make any provider-network requests. No live provider searches, device/browser acceptance, full upstream regression suite, or production security acceptance have been verified. This local environment still reports SQLite threading warnings; the local engine registry contains only `brave` and `startpage`. In particular, Startpage functionality and proof-of-work challenge behavior have not been verified with live provider traffic.

## Source boundaries

- [SearXNG provenance and AGPL obligations](UPSTREAM.md)
- [Partial Glaze implementation and acceptance gaps](GLAZE-INTEGRATION.md)
- [Capability roadmap](docs/goreecloud/ROADMAP.md)
- [Local JSON source-selection extension](docs/goreecloud/LOCAL-JSON-API.md)
- [Upstream SearXNG documentation](README.rst)

Pre-reset GoreeCloud Search code persists on historic branches; this import does not automatically provide or authorize GoreeCloud Index, Identity, Privacy Shield, Wardveil Security, or Everkeep integration.
