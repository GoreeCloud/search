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

## Source-only HTTP denial classification follow-up

The runtime logs above distinguish HTTP 429 and HTTP 403, but the existing
online-engine processor catches both as generic `curl_cffi` HTTP errors,
so the public unresponsive-engine contract only says `HTTP error`.
A subsequent **source-only** correction maps a numeric `HTTPError.response`
status of 429 to `SearxEngineTooManyRequestsException` (rate-limit suspension)
and 403 to `SearxEngineAccessDeniedException` (access-denial suspension).
Other HTTP/network errors keep their previous handling; the processor no
longer logs exception string details that might contain a query or upstream
URL. These mappings are covered by synthetic tests without real-provider
egress. **They have not been exercised with another live upstream probe**:
provider accessibility remains unqualified and upstream limits must not be
circumvented.

## Private result-page retry behavior for upstream denials

A separate **source-only** UI safeguard checks the canonical internal failure
classes for the user's exact selected sources, not translated error strings.
If **every** selected source reports rate limiting, CAPTCHA or access denial,
the no-results page explains that the providers are currently refusing
requests and suppresses immediate same-source retry and previous-page POST
forms. Users can start a fresh search and explicitly choose another approved
provider. If even one selected provider is not access-restricted (including
ordinary timeout, network failure, or missing failure reports), the previous
explicit retry behavior remains available; there is no silent provider swap.
This is UI guidance, **not** server-side prevention of all manual searches or
a substitute for existing engine suspension and rate-limit enforcement.
Offline Flask page tests verify first-page, later-page and partial-source
cases without contacting external providers.

## Provider-health proof gate (source-only)

The offline/opt-in `scripts/provider_health_probe.py` previously classified any
nonempty `results` list as `results_observed` when the intended provider
was selected. Selected-engine metadata is not evidence that a result actually
came from that provider. The hardened probe now requires that each result
have a safe public HTTP(S) primary URL and exact single-provider attribution,
and checks the represented-source list/count and explicit no-contact-proof
flag. Wrong-source results, unsafe or malformed links, and inconsistent
representation fail closed with bounded diagnostic states; result text, URLs
and user search terms are never echoed. Synthetic offline tests cover these
conditions across approved categories. **Matching these labels still does
not prove live upstream access.** Follow-up offline hardening rejects
alternate numeric IPv4 hosts (integer, octal, hex forms), non-public literal
IPs, special-use local DNS suffixes, invalid hostname labels and ambiguous
URL authorities. None are fetched, resolved or logged. Public DNS names can
still rebind to private IPs, so a verified network egress firewall remains
mandatory; syntax checks cannot prove DNS safety. No provider queries are
authorized or triggered by these source-only changes.

Further source-only negative tests now enforce the complete private JSON
selection/representation metadata on **empty results and upstream failures**,
not only successful result lists. Missing or contradictory selection counts,
proof disclaimers or zero-result representation labels return bounded invalid
contract states, never `no_results` or `provider_error` evidence. The online
engine processor also omits raw SSL, access-denial and parser exception text
from its debug messages: these strings may embed upstream URLs, response
fragments or search terms. Existing exception classes and suspension behavior
are retained; this redaction is not a claim that all possible server logs or
metrics are sanitized. These checks exercised only synthetic local failures,
with no real provider requests or changes to the isolated VPS.

An October 23 offline DuckDuckGo Web follow-up removed adapter DEBUG logs
that previously included the full form body (including a user's query),
headers, cookies, and cached `vqd` continuation token. The adapter now emits
only fixed messages. A returned HTTP 303 redirect, previously misrepresented
by the Web parser as an empty successful result, instead yields a bounded
engine API error without following the redirect. Synthetic tests verify
redaction and redirect rejection; these source changes were **not** validated
against live providers. A previous Development staging query showing results
alongside DuckDuckGo/Startpage errors is only point-in-time evidence, not
proof that either provider is consistently available. No additional probe,
provider bypass, retry or default-source change was introduced here.

The subsequent offline Startpage response-attribution guard now rejects any
search response or form-token homepage response that arrives from a different
or ambiguously encoded origin, even if its body resembles valid Startpage
markup. Explicit recognized CDN access-denial pages retain their bounded
`SearxEngineAccessDeniedException` classification; other off-origin responses
use a fixed engine API error without printing the response URL or caching a
foreign form token. Synthetic tests cover lookalike hosts, HTTP downgrade,
credential-bearing authorities, unexpected ports, malformed URLs, legitimate
Startpage hosts, and protected blocked-page behavior. This validates only
source-contract resilience; actual Startpage access and provider rights remain
unqualified until separately authorized, representative live evidence exists.

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
