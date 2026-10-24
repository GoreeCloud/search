# GoreeCloud Search — free-category smoke verification

**October 20, 2026 · Development · NetBird-restricted site · No paid APIs**

## Objective and boundaries

Measure whether live free SearXNG returns **actual result links** for General, Images, Videos and News, not merely HTTP 200, engine names, or an empty-state page. Do not modify Caddy/NetBird routes, provider lists, public access, billing, Tor, persisted search data or production containers.

The historical observations below used the PR #65 free-first canary image `goreecloud/search:staging-195b809575dd` at source commit `195b809575ddd1e5dc68ebcaabf832e8d349931c`. The later, separately verified [working-free-sources Development cutover](../../deploy/vps/FREE-WORKING-SOURCES-CUTOVER.md) now routes the NetBird-restricted `https://search-dev.goreecloud.com` to source `40caeb47a1fd8fc15a60f54e5e383d1a9f280598`; the retained free-upgrade service is a rollback candidate. The smoke tool remains **developer-side verification code**, not a scheduled or deployed monitor.

## Recorded observations, one bounded test per category

A previously tested news query about library archives returned HTTP 200 with **zero** results; that alone did not establish the News category was broken. A topical `NASA Artemis` query against the free DuckDuckGo News public adapter independently returned **29** results with no reported failure.

This fixed-fixture smoke tool uses nonpersonal, subject-appropriate queries and confirms selected adapter identities in the JSON response. A single complete live NetBird HTTPS run of `scripts/free_category_smoke.py` observed:

| Category | Explicit free engine selection | Valid result links | Unresponsive engines | State |
| --- | --- | ---: | ---: | --- |
| General | DuckDuckGo, Bing, Startpage | 18 | 0 | Results observed |
| Images | DuckDuckGo Images, Bing Images | 35 | 1 | **Partial results with provider error**; Bing returned results, DuckDuckGo Images failed |
| Videos | DuckDuckGo Videos, Bing Videos | 95 | 0 | Results observed |
| News | DuckDuckGo News | 29 | 0 | Results observed |

HTTPS readiness was HTTP 200 / READY with certificate verification enabled. Results are counted only when the structured JSON response identifies the expected selected engines and contains nonempty titles and syntactically valid, nonlocal HTTP(S) destination URLs. **Counts measure observed result links, not independent provider reachability or guarantee of future topical matching.** A provider may be selected but not respond; do not infer all selected providers were available merely from a combined result count. **Any reported engine failure now produces a nonhealthy partial-result state, even when another selected engine supplies enough links.** The tool emits only exact preapproved selected engine labels, not third-party error messages or private URLs. Never silently replace a denied source.

### October 21 source-contract tightening (Development source only)

The category checker now fails closed when a returned result has a malformed or nonpublic destination (including numeric/octal loopback aliases, link-local addresses, credential-bearing URLs, control characters and reserved private hostnames), missing title, or an unselected/unknown source attribution. It also cross-checks each result's primary and merged engine labels against the response's represented-engine counts, selected-engine count and explicit **not a provider-contact confirmation** markers. Malformed or unrecognized provider-error attribution is rejected without printing raw error details.

These checks consume **no additional requests** and perform no DNS resolution. Local fixtures cover public links, merged attribution, wrong-source responses, false counts and unsafe URLs. The historical observed numbers in the table above were collected before this tightening; they must **not** be presented as a new live pass of the stricter checker. The tested-free-source preset separately uses Bing Images by default; this explicit two-engine diagnostic deliberately includes DuckDuckGo Images to expose its unresolved partial failure. No deployment or provider probe was performed for this source-only change.

## Reproduce through authorized NetBird connection

From an authorized computer with access to this repository and the installed Search Python dependencies:

```sh
python scripts/free_category_smoke.py
python scripts/free_category_smoke.py --category news
python -m unittest discover -s tests/goreecloud -p 'test_free_category_smoke.py' -v
```

One complete invocation sends exactly **one readiness GET and four synthetic search POSTs**, spaced one second apart. `--category` reduces its scope. There is no configurable target URL: the only HTTP destination is the fixed HTTPS Development hostname. Normal certificate validation is required. The tool disables inherited environment proxies, never follows redirects, and never prints queries, links, result content, tokens or provider exception messages. It does not save responses. These checks consume the existing global 12-searches/minute budget; avoid parallel full checks, manual rapid retries or use while busy searching.

A zero-result state is not automatically proof of a provider outage: first consider topic relevance, category availability and a temporary upstream failure. Rate limits, 403/429, bot checks and CAPTCHAs must not be circumvented. This diagnostic tool is **not** a general SSRF test, a public uptime service, a replacement for the ChatGPT hourly conditional health watch, or an endorsement of any provider's terms.

## Remaining acceptance gates

- Confirm repeatability over several days and at different times; a one-time category result is insufficient for Stable.
- **Isolated failure:** one bounded per-engine test of the same public NASA photo query returned DuckDuckGo Images HTTP 200 / 0 results / 1 engine failure and Bing Images HTTP 200 / 35 results / 0 failures. This supports a DuckDuckGo Images-specific adapter/provider failure, **not** a proven cause (e.g., 403, parser break or rate limit). Do not probe upstream repeatedly or bypass controls. The diagnostic CLI now fails the category health check when a selected provider reports a failure; it does not suppress the working Bing Images results.
- Independently qualify each selected adapter: combined result counts do not prove every engine returned results.
- Continue validating that the NetBird-only HTTPS client restriction, per-worker request budget, backup/rollback, and Caddy recovery remain intact; do not widen access.
- Separate stable-branch promotion, signed release provenance, appropriate security/data-restoration verification and long-duration monitoring remain open. Keep current live Development status until independently accepted.

**No new subscription, paid API call, vendor account, Tor requirement or user-query logging was introduced.**
