# GoreeCloud Search

Privacy-focused, configurable federated search rebuilt from the SearXNG source engine toward GoreeCloud platform standards.

**Lifecycle:** Development only. The [VPN-only VPS deployment profile](deploy/vps/README.md) is not a public release. **Upstream:** SearXNG `f4822b3`. **Glaze:** V1.7 / 1.7.0 inherited foundation, partial mapping (not formally accepted).

## Native Search foundation (isolated Development)

The experimental [native Search foundation](docs/goreecloud/NATIVE-SEARCH-FOUNDATION.md)
provides a separately testable SQLite FTS5 index, an explicitly seeded HTTPS
crawler, and a loopback-only JSON search service. Its approved-document index
is available only as a separately enabled Development source: it does **not**
replace SearXNG, automatically join the seven-family All Sources federation,
index the general web, or schedule crawling. Whether that opt-in source is
available depends on the deployed Development configuration. Publisher
permissions and production/privacy qualification are required before broader
crawling or rollout.

## Working implementation

The private Development profile offers seven approved upstream provider families: **Brave Search, Startpage, Qwant, DuckDuckGo, Ecosia, Bing and Google**. **All Sources** is the default and merges/deduplicates matching results with source attribution; single-provider selection remains in Settings. Web supports all seven, Images and News support six (except Ecosia), and Videos supports five (except Ecosia and Startpage). Other inherited SearXNG providers, including the Brave API, remain excluded. The private profile defaults to SafeSearch **None**, with user-controllable restrictions. Local HTML search and an unauthenticated loopback-only JSON extension remain available; neither provider inclusion nor a green test establishes real provider reachability. GoreeCloud Index, AI answers, business search, and alerting are not part of this implementation.

## Owner-approved homepage design

The October 11 desktop/mobile owner mockups established the Search visual direction; later owner feedback refined the responsive GoreeCloud/Glaze branding, prominent result cards, a cleaner homepage, category tabs (Web, Images, Videos, News), improved Settings and image gallery behavior. See [Official homepage](docs/goreecloud/OFFICIAL-HOMEPAGE.md) for the historical design baseline and [Settings and category navigation](docs/goreecloud/SEARCH-CATEGORIES-SETTINGS-UX.md) for the updated category contract. Search still submits queries via POST. Privacy slogans state design aims, not a promise that external providers do not track queries.

## Develop locally

Follow [upstream SearXNG development instructions](docs/dev/index.rst) to install dependencies. Set a unique 32+-character secret in a local secret store, and launch through the fail-closed wrapper:

```sh
export SEARXNG_SECRET="<unique-strong-secret-from-your-secret-store>"
./scripts/run-private.sh
```

Never use the upstream placeholder key. The profile binds **127.0.0.1**, disables metrics and remote autocomplete, proxies images, defaults to POST, and exposes opt-in JSON on a private interface. No other upstream engine is registered as an available search option. Startpage has an upstream proof-of-work anti-bot challenge, so inclusion and enabled state do **not** establish that real Startpage searches work. It does **not** implement public rate limiting. Internet exposure requires a separate gated HTTPS/reverse-proxy, Valkey limiter, hardened secrets, security/privacy and operational acceptance.

## Private search disclosure safeguards

The local profile now rejects query-bearing GET requests, preserves POST even on Android/WebKit, and disables caching for private search pages. It also refuses non-loopback Host headers and browser cross-origin/cross-site form submissions before any search dispatch (a limited DNS-rebinding/CSRF defense), and caps search/preview form bodies at 64 KiB. Local non-browser clients can omit Origin headers; browser POSTs with opaque `Origin: null` are accepted only when `Sec-Fetch-Site: same-origin` explicitly confirms local origin, matching a verified Chromium form submission. This limited boundary defense is not a substitute for public authentication or abuse prevention. Query-length and distinct-provider limits are set to 512 characters and **seven provider families** respectively; searches exceeding these limits return 413/422 rather than silently expanding disclosure. Private result pages omit query-bearing RSS/share URL metadata, and the private homepage does not advertise OpenSearch GET-query registration; the private server also returns uncached 404 responses for direct OpenSearch and autocomplete endpoints until an appropriately safe browser integration is qualified. The privacy-sensitive preferences for POST transport, title disclosure, autocomplete, favicons, and image proxy are locked against cookie and request overrides. The private profile also rejects external-bang redirects and first-result (double exclamation mark) navigation before dispatch; unexpected provider/plugin redirects are refused instead of navigating the browser to a third-party site. Query length is validated on the submitted value before operator parsing. The explicitly allowlisted provider shortcuts cover Brave, Startpage, Qwant, DuckDuckGo, Ecosia, Bing and Google, plus general/web category shortcuts. Unknown or third-party bangs are rejected rather than silently falling back; unsupported providers cannot be selected or dispatched. Shared serialized-preference GET/POST imports are rejected before parsing because upstream can otherwise change selected providers by following a URL; regular local Preferences forms remain available. Primary HTML/JSON search result links are restricted to well-formed HTTP(S) addresses, rejecting malformed or zero ports and invisible Unicode control characters. These safeguards do not cover all embedded or secondary URLs, cannot prevent configured upstream providers from receiving queries, and do not establish anonymity or production security acceptance.

## Relay and anonymity qualification

All seven configured provider families require the approved local SOCKS5H proxy,
including image-proxy traffic; there is no authorized direct fallback. **A SOCKS5H
setting does not prove that the relay is Tor.** On this Development candidate the
effective `outgoing.using_tor_proxy` setting is false, so the SearXNG Tor-exit
attestation is **not yet enforced**. Before any promotion, integrate the positive
Tor-exit guard, qualify fail-closed behavior across provider and image sessions,
and verify relay identity, DNS isolation, and rollback in the target environment.
The upstream providers can still receive the plaintext search terms over HTTPS,
and browser clicks can reveal client details to result destinations. See
[security boundaries](docs/goreecloud/SECURITY-BOUNDARIES.md) and
[draft Search PR #29](https://github.com/GoreeCloud/search/pull/29).

## Controlled provider diagnostic (Development only)

`scripts/provider_health_probe.py` is an explicitly opt-in, HTTP loopback-only
**Web-provider diagnostic**, not a live availability or Tor anonymity monitor.
Without the egress flag, every mode performs **zero requests**:

```sh
python scripts/provider_health_probe.py --provider all
```

The expanded `all` mode names Brave, Startpage, Qwant, DuckDuckGo, Ecosia,
Bing and Google. The original `both` mode/default remains the **legacy
three-provider** Brave/Startpage/Qwant sweep to avoid silently increasing
previously authorized requests. A single provider can be selected by name.

**Do not run with `--allow-provider-egress` until a trusted Development
loopback listener and independently verified Tor exit/DNS safeguards exist.**
With that explicit opt-in, the tool sends fixed synthetic terms by POST, refuses
redirects, validates selected-source metadata, and reports only provider states
and counts. It does not save query terms or response bodies. Running it cannot
establish all-category availability, privacy, publisher permission, or release
acceptance. No real-provider tests were executed for this feature.

## Search preview (no provider requests)

The loopback-only **POST /preview** contract inspects selected sources, categories, language and SafeSearch without dispatching a provider request. The homepage does not expose source picker or preview controls; the saved source preference is managed in Settings. Results prioritize web matches and keep provider attribution, failure details, retry and source refinement in secondary controls. Follow-up POST actions preserve validated provider selection and query context without placing terms in URLs. The preview and execution policies enforce the same 512-character input limit and seven-family fanout cap. Preview metadata is not evidence of provider contact, availability, or consent.

When Startpage is among the selected sources, the HTML preview also warns about its unverified anti-bot proof-of-work behavior and confirms no substitute provider is used. Search can be focused with `/` from non-editable page content without triggering network requests or interfering with slash typed inside a search input.

The same private local preflight is available through `POST /preview` with `q` and `format=json` in the **body**; its response includes only query length, selected engines/categories and explicit `network_requests_made: false`, not raw query terms. GET to this endpoint is rejected and uncached; the route is unavailable outside the local private profile. The API is not authenticated and must remain loopback-only.

## Search experience

Results display separate selected-source and represented-source summaries: selected engines show which upstream choices were made, while per-engine counts show source labels attached to the safe web results actually displayed. A result aggregated from multiple approved adapters can contribute to each count; neither list confirms network contact, authenticates upstream providers, or proves every engine responded. The loopback JSON extension exposes the same represented-source counts. The search header uses GoreeCloud branding, with accessible search labels and responsive Glaze styling. An empty search provides local preference guidance instead of sending users to another service. Privacy policy refusals now have an accessible recovery screen that never reflects query text; local JSON callers receive a structured policy error. These interfaces are source- and Flask-render validated but still need browser, screen-reader, and visual acceptance.

## Local readiness diagnostics

The loopback-only Development profile exposes `GET /readyz`. It returns `200 READY` only when at least one configured, enabled provider processor registered at startup; otherwise it returns `503 NOT_READY`. It reports no provider names or user data. The original `/healthz` liveness route remains unchanged. Readiness is an **in-process startup check**, not proof that any external search provider is reachable, authorized, safe or responding. It is hidden (404) when the private profile is disabled; public operations require a separately authenticated and reviewed health contract.

## Development validation

With SearXNG's pinned requirements installed (including the Python 3.10 compatibility backport when applicable), run the commands below. GitHub source/runtime CI now checks both Python 3.10 and 3.12, while the Chrome browser job uses Python 3.12:

```sh
python -m compileall -q searx
python -m unittest discover -s tests/goreecloud -v
# Independent native-index, bounded crawler and approved-corpus tests:
python -m compileall -q native_search
python -m unittest discover -s tests/native -p 'test_*.py' -v
python -m pip install nose2==0.16.0 aiounittest==1.5.0 parameterized==0.9.0 mock==5.2.0
export SEARXNG_SECRET="$(python -c 'import secrets;print(secrets.token_hex(32))')"
python -m nose2 -s tests/unit test_query test_webadapter test_settings_loader test_webapp -v
```

At the seven-family Development source checkpoint `d75b57c8f32e2b909a78fcb831155f9eba83d49d`, two exact-head workflows passed independently: [GoreeCloud Search foundation run 39172183106](https://github.com/GoreeCloud/search/actions/runs/39172183106) with **4/4 jobs** (Python 3.10/3.12 application contract and 72 targeted upstream regressions, browser smoke and private Granian listener), and [Native Search Development run 39172183097](https://github.com/GoreeCloud/search/actions/runs/39172183097) with **2/2 jobs** (all **23 native tests** plus fixture-indexing smoke on Python 3.10 and 3.12). The native workflow now runs for all branch-push and pull-request candidates, rather than only changes to native-source paths. The application test matrix remains separate; it is not necessary to pretend those same native tests were added to its workflow.

The Ecosia adapter classifies unparseable organic cards as provider errors, not legitimate empty results; its dedicated malformed-card regression fixture is still uncommitted. The native index remains an opt-in Development source, not automatically part of All Sources. Both passing CI workflows verify bounded offline contracts, **not** live seven-provider availability, Tor anonymity, public authentication, abuse limits, screen-reader/Glaze acceptance or production readiness. Python 3.10 produces SQLite threading diagnostics while Python 3.12 does not; passing tests cannot establish SQLite concurrency safety in the target deployment. The Development configuration does not include a production public rate limiter. Real source compatibility, provider challenges/429s, Tor exit/DNS leak and relay recovery, security authorization and recovery/rollback qualification remain open.

Git version metadata now resolves local branches without upstream tracking (including detached-HEAD checkouts) instead of assuming an upstream `master` branch. This is a diagnostic reliability fix; it does not affect network requests or provider selection.

## Source boundaries

- [SearXNG provenance and AGPL obligations](UPSTREAM.md)
- [Partial Glaze implementation and acceptance gaps](GLAZE-INTEGRATION.md)
- [Capability roadmap](docs/goreecloud/ROADMAP.md)
- [Local JSON source-selection extension](docs/goreecloud/LOCAL-JSON-API.md)
- [Upstream SearXNG documentation](README.rst)

Pre-reset GoreeCloud Search code persists on historic branches; this import does not automatically provide or authorize GoreeCloud Index, Identity, Privacy Shield, Wardveil Security, or Everkeep integration.
