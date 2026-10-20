# GoreeCloud Search — free-category smoke verification

**October 20, 2026 · Development · NetBird-restricted site · No paid APIs**

## Objective and boundaries

Measure whether live free SearXNG returns **actual result links** for General, Images, Videos and News, not merely HTTP 200, engine names, or an empty-state page. Do not modify Caddy/NetBird routes, provider lists, public access, billing, Tor, persisted search data or production containers.

Source base is GoreeCloud Search's currently deployed free-first canary from PR #65: pinned running Search image `goreecloud/search:staging-195b809575dd` at source commit `195b809575ddd1e5dc68ebcaabf832e8d349931c`. Its live HTTPS route at `https://search-dev.goreecloud.com` requires authorized NetBird connectivity. The original Search/Tor pair remains a rollback path. The smoke tool here is **developer-side verification code**, not yet an automatically deployed service.

## Recorded observations, one bounded test per category

A previously tested news query about library archives returned HTTP 200 with **zero** results; that alone did not establish the News category was broken. A topical `NASA Artemis` query against the free DuckDuckGo News public adapter independently returned **29** results with no reported failure.

This fixed-fixture smoke tool uses nonpersonal, subject-appropriate queries and confirms selected adapter identities in the JSON response. A single complete live NetBird HTTPS run of `scripts/free_category_smoke.py` observed:

| Category | Explicit free engine selection | Valid result links | Unresponsive engines | State |
| --- | --- | ---: | ---: | --- |
| General | DuckDuckGo, Bing, Startpage | 18 | 0 | Results observed |
| Images | DuckDuckGo Images, Bing Images | 35 | 1 | Results observed, one engine still needs diagnosis |
| Videos | DuckDuckGo Videos, Bing Videos | 95 | 0 | Results observed |
| News | DuckDuckGo News | 29 | 0 | Results observed |

HTTPS readiness was HTTP 200 / READY with certificate verification enabled. Results are counted only when the structured JSON response identifies the expected selected engines and contains nonempty titles and syntactically valid, nonlocal HTTP(S) destination URLs. **Counts measure observed result links, not independent provider reachability or guarantee of future topical matching.** A provider may be selected but not respond; do not infer all selected providers were available merely from a combined result count. Never silently replace a denied source.

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
- Investigate the single image-engine unresponsive report without excessive probes or bypassing upstream controls.
- Independently qualify each selected adapter: combined result counts do not prove every engine returned results.
- Continue validating that the NetBird-only HTTPS client restriction, per-worker request budget, backup/rollback, and Caddy recovery remain intact; do not widen access.
- Separate stable-branch promotion, signed release provenance, appropriate security/data-restoration verification and long-duration monitoring remain open. Keep current live Development status until independently accepted.

**No new subscription, paid API call, vendor account, Tor requirement or user-query logging was introduced.**
