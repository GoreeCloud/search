# Free DuckDuckGo media adapter — fail-closed token handling

**October 20, 2026 · Development candidate · No paid API, bypass, or live deployment.**

## Verified symptom

On the free-first `search-dev.goreecloud.com` Development service through the authorized NetBird HTTPS client, a bounded public NASA photo query selected only `duckduckgo images` and yielded **HTTP 200 from GoreeCloud Search, zero images, one unresponsive engine report**. The same query using `bing images` returned **35 results and zero engine failures**. A separate bounded repetition of DuckDuckGo Images again yielded zero/one. Limited recent Search container logs (inspected and aggregated **without exposing query strings or URLs**) contained two lines that mentioned both `duckduckgo images` and `403`. This is evidence of an upstream access restriction being reported, but **not** proof of the exact denied endpoint, all HTTP exchanges, or the long-term blocking policy.

The upstream SearXNG `duckduckgo_extra` media adapter obtains a query validation digest (`vqd`) before constructing `/i.js`, `/v.js`, and `/news.js` requests. Before this change, a 403, 429, other non-200 response, or HTTP 200 lacking `vqd` could return an empty token and still construct a second JSON endpoint request with `vqd=`. Those extra requests are invalid and can make provider access controls worse, not better.

## Corrective behavior

- Stop at the **first denied token response**: HTTP 403 raises SearXNG's standard `SearxEngineAccessDeniedException`; HTTP 429 raises `SearxEngineTooManyRequestsException`, allowing SearXNG's configured engine suspension policies to apply. **Do not retry, change identity, solve a CAPTCHA, or change the destination.**
- HTTP 200 without a token and unexpected non-200 responses raise `SearxEngineAPIException`. An empty cached/fetched token cannot produce a media JSON endpoint request.
- On an ordinary HTTP 200 with a nonempty token, preserve SearXNG's cache and media request behavior. Remove raw token, request header, cookie, and payload debug logging from this adapter.
- Keep DuckDuckGo Images **visible and selectable** and leave the currently functioning Bing Images and all other public interfaces unchanged. This fail-closed fix does **not** restore DuckDuckGo availability while the upstream denies the request.

## Acceptance and rollout boundaries

Run offline synthetic-response regression tests in `tests/goreecloud/test_duckduckgo_extra_fail_closed.py`, the entire Search contract suite and exact-head GitHub CI. Test any new image in **disposable isolation** before a governed live swap. The current healthy free Search canary `goreecloud/search:staging-195b809575dd` remains the known-working baseline; the original private Search/Tor containers and protected Caddyfile backup remain the tested route recovery path.

Do not call GoreeCloud Search Stable from adapter tests. Maintain the owner-selected free/no-subscription/no-special-Tor model, NetBird access restrictions, bounded requests, and truthful provider failure reports. Upstream terms, sustained availability, category coverage, signed provenance and production recovery still require separate qualification.
