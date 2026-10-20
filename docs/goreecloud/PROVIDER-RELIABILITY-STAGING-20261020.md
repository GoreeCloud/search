# GoreeCloud Search — isolated Tor provider reliability investigation

**Date:** October 20, 2026
**Classification:** Development-only, synthetic provider probe
**Qualification:** **FAILED — zero successful Web-provider results; do not promote**
**Running live service:** unchanged older Development image
`goreecloud/search:dev-parser-56a4823`

## Purpose and privacy boundary

Qualify **real** Web-source compatibility over the isolated Search/Tor gateway,
not merely source inclusion, homepage labels, a successful API status or Tor
bootstrap. Only one fixed synthetic POST search per provider was used in the
initial sweep. No real user query, cookie, address, provider result text or URL
was recorded in the report. Responses were parsed only for approved-source
selection, result/error counts, generic error category and elapsed time.
Challenges, HTTP 403, and HTTP 429 must not be bypassed by direct fallback,
proxy downgrade, CAPTCHA solving or increased request volume.

The isolated Compose project places Search solely on a Docker internal bridge;
only Tor attaches to the outbound bridge. Staging check verified that Search
was reachable only over loopback with HTTP 200 / READY, and the internal bridge
still blocked tested direct public/private/metadata IPv4 and external DNS.
Image `goreecloud/search:staging-d828a1c556df` came from the pinned
Development commit `d828a1c556dfb7ed111525af91a19fb6973a8931`.
The **first sweep** used the original three-second HTTPS-engine deadline.

## Initial seven-provider Web sweep

| Source | Results | Search API | Staging finding |
| --- | ---: | --- | --- |
| Brave | 0 | HTTP 200, provider error | Upstream HTTP **429** in redacted application logs |
| Startpage | 0 | HTTP 200, provider error | Deadline reached at approximately 3 seconds |
| Qwant | 0 | HTTP 200, provider error | Deadline reached at approximately 3 seconds |
| DuckDuckGo | 0 | HTTP 200, provider error | Upstream HTTP **403** in redacted logs |
| Ecosia | 0 | HTTP 200, provider error | Upstream HTTP **403** in redacted logs |
| Bing | 0 | HTTP 200, provider error | Deadline reached at approximately 3 seconds |
| Google | 0 | HTTP 200, provider error | Upstream HTTP **403** in redacted logs |

All responses selected the requested single source and returned an
`unresponsive_engines` entry. **HTTP 200 indicates an API response only, not
provider success.** API-facing translated error text sometimes collapses
different HTTP status codes to `HTTP error`, so CLI diagnostics must report a
bounded generic `upstream_http_error` rather than inventing 403 or 429.
The redacted staging logs provided the observed HTTP statuses listed above.

## Root-cause correction and narrow retest

The private `configs/goreecloud/settings.yml` previously inherited upstream
`outgoing.request_timeout: 3.0`. Its
`outgoing.extra_proxy_timeout: 10` does **not** extend ordinary HTTPS
providers; SearXNG applies that extension to eligible onion adapters.
The Development candidate now explicitly sets **request_timeout=12.0** and
**max_request_timeout=12.0**. The bounded deadline is a diagnostic and
reliability correction, not a license to slow-query or bypass privacy controls.

A clean isolated VPS staging run using configuration candidate
`68dfab6b03ce487ba0e3edbb6780d94b1dcdcfe5` and the existing
`d828a1c556df` code image verified the active 12-second settings, local
private Tor profile, internal network and HTTP 200 readiness. Only the
three originally timed-out Web providers were retried, **once each**:

| Source | Elapsed | Results | Bounded diagnostic |
| --- | ---: | ---: | --- |
| Startpage | ~8.0 s | 0 | Network error |
| Qwant | ~2.6 s | 0 | Access denied |
| Bing | ~0.4 s | 0 | Network error |

The three-second premature deadline was removed, allowing more informative
failures, but **none returned a usable result**. Do not conflate this mixed
config/image rehearsal with a rebuilt candidate image test. No broader sweep
was retried; explicitly rate-limited or access-denied sources were left alone.

## Next release acceptance gates

- Confirm a sustainable provider access path that preserves GoreeCloud's
  approved provider policy, user-query privacy and contractual/technical
  restrictions. Do not circumvent CAPTCHA, HTTP 403 or HTTP 429; do not
  silently substitute providers or mislabel results.
- Distinguish timeout, network failure, rate limit, access denial, parser/API
  incompatibility and genuinely empty search responses through **bounded
  diagnostic categories** without exposing provider URLs or search terms.
- Review whether a 12-second latency ceiling is acceptable for real users
  before adoption; test category-specific Web, Images, Videos and News
  adapters only after the relevant Web/provider prerequisites are met.
- Preserve the original working service, separate staging, exact pinned image
  provenance, Tor DNS/IPv6/metadata isolation, ingress/limiter acceptance,
  and tested rollback. Passing infrastructure tests is not provider success.
- Earlier staging startup also attempted to refresh tracker patterns from
  third-party hosts; internal network DNS denial prevented resolution. Audit
  and explicitly govern such auxiliary outbound behavior before production.

**Teardown:** The revised staging trial ended with complete removal of its
three containers and two networks. The unrelated original Search/Tor pair
remained running; live Search reported **healthy**.

**Conclusion:** seven-provider Web reliability is **NOT QUALIFIED**. Keep
[GoreeCloud/search issue #26](https://github.com/GoreeCloud/search/issues/26),
[network issue #21](https://github.com/GoreeCloud/search/issues/21), and
[release roadmap #1](https://github.com/GoreeCloud/search/issues/1) open.
