# GoreeCloud Search — approved-provider access and release-evidence decision

**Reviewed:** 2026-10-20
**Environment at original review:** seven-provider candidate, *not* deployed on October 20 at the time of the initial probe. Later private Development deployments are documented below.
**Decision:** provider-results reliability NOT QUALIFIED; keep issues #26, #21 and #1 OPEN
**Owner clarification (2026-10-20):** Prefer Zero Data Retention (ZDR) for authenticated upstream APIs, but do not make ZDR an absolute blocker to stabilizing GoreeCloud Search. This is a priority trade-off, **not authorization to activate a standard-retention provider, purchase a plan, or weaken private egress**.

## October 23, 2026 — native fusion rights checkpoint

GoreeCloud's owner has specified **one GoreeCloud-owned metasearch result stream**
combining Google, Bing and Brave where lawfully possible. This is the target
product contract, **not** permission to call, merge, cache or redistribute
these providers' results today. Source selection, result acquisition, right to
transform/rerank, display, storage and query disclosure are separate decisions.

First-party vendor documentation was checked again on October 23:

| Intended source | Official status/term observed | Current native fusion admission |
| --- | --- | --- |
| **Google** | Custom Search JSON API is **unavailable to new customers** and scheduled to stop January 1, 2027, including its Web and Images offerings. | **Deny** new API onboarding; only a separately identified, actually available product with explicit category/usage rights could be reconsidered. |
| **Microsoft Bing** | Standalone Bing Search APIs were retired August 11, 2025; Azure AI Grounding with Bing is described for AI agents and is **not verified as a raw-result metasearch feed**. | **Deny** retired API integration; investigate an authorized replacement only with documentary evidence of SERP access and reuse. |
| **Brave Search API** | Terms last updated September 1, 2026 grant bounded use with customer applications but prohibit non-transient result storage, derivative works of Search Results, redistribution/resale/sublicensing and using results to replace API functionality. | **Deny by default** for fusion/reranking until Brave's applicable agreement or written approval explicitly covers GoreeCloud's exact metasearch output and handling. Mere API-key availability is insufficient. |

This is a conservative engineering admission decision, **not a legal opinion**
or a claim that every hypothetical arrangement is prohibited. Terms and actual
entitlements may differ under a signed order or amendment. The public product
must never imply it obtains all three feeds unless representative authorized
results from each source have passed independent live acceptance.

### Provider-specific evidence required before an adapter can leave fixture mode

Record one independently verifiable authorization decision **per source and
category**, containing the approved exact endpoint/product, account or order
scope (without secret material), permission to request results, permission to
combine and rerank, permission to display the combined cards, derivative-work
conditions, mandatory attribution, allowed transient cache lifetime, result
retention/deletion, query privacy and applicable geographical limits. Also
record effective terms date, provider contact/contract reference and renewal
review. A generic `enabled: true` or a successful network response does not
provide this evidence.

The runtime must default to **no upstream request** when any mandatory right
or endpoint cannot be established. License-denied, 401/403, 429, CAPTCHA,
timeout, malformed response and empty-but-successful search are different
states; never disguise a denial as zero results or silently replace one source
with another. Never persist provider results beyond an expressly authorized
transient operational window. These policies apply to images, thumbnails,
videos, news, shopping/local data and snippets separately, not just Web URLs.

Official sources (accessed October 23, 2026):

- https://developers.google.com/custom-search/v1/overview
- https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement
- https://api-dashboard.search.brave.com/documentation/resources/terms-of-service

**Source/runtime distinction:** the offline GoreeCloud-owned fusion primitive
on Development is synthetic-only. The private deployed Search runtime still
uses the earlier SearXNG-derived Working preset; its Bing Images results are
not evidence of a supported Microsoft Bing JSON API or of licensed native
fusion. `search-dev.goreecloud.com` remains private through NetBird. A public
`search.goreecloud.com` release requires independent acceptance and has **not**
been established by this document.

## Evidence and supported-access options

The October 20 isolated Tor staging trial used one fixed synthetic Web query
per approved provider and returned **zero usable results**. Redacted upstream
logs showed Brave 429; DuckDuckGo, Ecosia and Google 403; Startpage, Qwant and
Bing initially hit a three-second timeout. Correcting the explicit bounded
timeout exposed network/access failures, not valid results. Do **not** infer
production readiness from a successful application health check or offline CI.

| Source | Verified public official access information | Release decision |
| --- | --- | --- |
| Brave | Official Web Search API requires a secret subscription token, activated plan, and payment information even with promotional credits. Its API-customer privacy notice says account-associated queries may be retained for up to 90 days for billing and troubleshooting | **Potential supported integration, not authorized or enabled**. First independently assess entitlement, billing, source attribution, API-use rights, and private Tor exit compatibility; never commit credentials or leak identifying account headers to unrelated endpoints |
| Google | Google's Custom Search JSON API is closed to new customers and scheduled to end for existing customers on **2027-01-01**. Google directs new use cases toward different enterprise/search offerings | **Do not build a new integration on the sunset API.** Any alternative must be separately licensed, evaluated for general Web-result suitability and privacy, and explicitly mapped to the actual credited provider |
| Bing | Microsoft's legacy Bing Search APIs were **retired 2025-08-11**. Grounding with Bing and Web IQ are newer AI/agent products, not confirmed as reusable organic-result APIs for this ordinary metasearch frontend | **Do not claim a direct JSON Search API replacement exists** or silently mark Bing as another provider |
| DuckDuckGo | Official help pages describe user-facing search and Instant Answers and report that traditional links/images are largely sourced from Bing | **No independent entitlement to programmatically redistribute full SERPs verified** from reviewed official pages; do not assume a user search page is a licensed API |
| Ecosia | Official documentation provides a browser search URL and autocomplete configuration, not proof of an approved machine-to-machine organic-results API | **Human/browser search instructions are not a general SERP API license** |
| Startpage | No supported programmatic organic SERP endpoint or automation agreement was verified during this review | Treat access rights, rate limits and stable interface as **unverified**; do not circumvent access denials |
| Qwant | Official help describes Web, Images, Videos and News search tabs, not an authorization for bulk programmatic result extraction | Treat a publicly viewable search page as **not** sufficient evidence of API rights |

Authoritative vendor pages reviewed:

- Brave API customer privacy notice (updated 2026-08-25): https://api-dashboard.search.brave.com/documentation/resources/privacy-notice
- Brave API Terms of Use (updated 2026-09-01): https://api-dashboard.search.brave.com/documentation/resources/terms-of-service
- Brave Web Search GET/POST reference: https://api-dashboard.search.brave.com/api-reference/web/search/get
- Brave API authentication: https://api-dashboard.search.brave.com/documentation/guides/authentication
- Brave API setup and plan terms: https://api-dashboard.search.brave.com/documentation/quickstart
- Brave product overview, free-credit and storage-rights notes: https://brave.com/search/api/
- Google's current API status: https://developers.google.com/custom-search/v1/overview
- Microsoft's legacy API retirement: https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement
- Microsoft's current Grounding with Bing product boundaries: https://www.microsoft.com/en-us/bing/apis
- Microsoft's Web IQ introduction (2026-06-02): https://blogs.bing.com/search/2026/6/Announcing-Microsoft-Web-IQ/
- DuckDuckGo source description: https://duckduckgo.com/duckduckgo-help-pages/results/sources
- Ecosia browser integration: https://support.ecosia.org/article/653-installing-ecosia-on-your-mobile-device
- Qwant user-facing categories: https://help.qwant.com/en/docs/qwant-search/searching/how-to-search-with-qwant/

These are provider-site/public-documentation findings, **not** contractual approvals,
account-entitlement checks, proof of Tor compatibility or operational probes.
Do not create an account, incur fees, bind a payment method, retrieve credentials,
or change source attribution under standing delegated authority alone.

## Privacy and viable access criteria

A supported integration must satisfy **all** of these independently:

1. Provider grants rights to retrieve and display relevant Web/Images/Videos/News
   results through the contemplated API/endpoint under the actual account and
   use case. Review terms and permitted storage, display, attribution and quota.
2. The provider works through the **approved egress profile of the exact
   candidate** with verified firewall, DNS/metadata/IPv6 boundaries and
   fail-closed checks. For the historical Tor-only candidate, separately
   verify SOCKS5H/Tor circuit use and absolutely no direct fallback; for the
   currently deployed free-first/direct-HTTPS Development profile, disclose
   that upstream providers can observe the VPS IP and submitted query. Never
   silently switch a candidate's promised egress model.
3. Decide whether an account-bound API key is acceptable to GoreeCloud's
   specific privacy promise. Where Tor is used it may hide the server IP while the token still links
   query history to one subscriber. Document this accurately and obtain
   applicable authorization for such a change in privacy model.
4. Strictly credit the actual provider (do not call one provider's result
   another's). Reject access-denied/rate-limited/challenge responses without
   bypassing or automatic substitution; bound cost, response size, fanout,
   timeout and secret exposure.
5. Confirm actual successful, representative, synthetic **provider results**
   for each claimed category, parser correctness, result-link safety,
   no-referrer/no-store behavior, sustained acceptable latency, and legal use.
   A successful HTTP response or search-worker instantiation does not qualify.

**Do not expand the approved seven-provider registry** or replace one brand with
a different vendor without a separate governed decision and precise UI labeling.

## Dormant Brave API adapter — source-only preparation

SearXNG already contains `searx/engines/braveapi.py`, but it remains
`inactive: true` in its defaults, absent from the GoreeCloud private
`keep_only` list, and explicitly **unapproved** by the private source registry.
No account or token has been provisioned. Existing `brave` Web/Images/Videos/News
source names still refer to the original HTML-based Brave connectors, not this API.

An offline-only correction now prepares the dormant Web adapter against the
vendor's documented API: HTTPS POST to the fixed official URL with the query
in a JSON body (not in a query-bearing URL), token accepted only through a
server-side configuration when separately authorized, explicit no-redirect
policy, supported freshness/offset/count limits, and correctly typed Web
results instead of video-result parsing. Invalid/malformed results and unsafe
URLs fail closed. Synthetic test tokens are not credentials. The API is
**not switched on and no queries are sent**.

**Material privacy decision required before any activation:** The Brave
**Search API customer** privacy notice says account-associated queries can be
retained for up to **90 days**; Tor only hides the network origin, not the
customer identity contained in a subscription token. Brave separately markets
enterprise Zero Data Retention; it must not be assumed for a standard plan.
Brave's public Search website privacy notice is *not* the API-customer
privacy contract. An authenticated subscription may also entail charges,
usage caps and restrictions on storing search results. Before activation,
confirm acceptable retention and attribution disclosures, account/plan
rights, privacy promises, terms, billing limits, Tor compatibility, secret
handling and isolated egress with an owner-authorized decision.

### Owner-approved retention preference — nonblocking for stabilization

The owner prefers **Zero Data Retention** where available, **but does not
want it to prevent or delay GoreeCloud Search stabilization**. Apply this
as a conditional preference, not a universal mandatory provider requirement:

1. **Proceed now** with offline parser/security tests, Tor/VPN/DNS isolation,
   category routing, supported-access research, performance, failure handling,
   source attribution and rollback preparation. These activities do not require
   Brave API credentials or a ZDR agreement.
2. **Prefer ZDR** for any eventual authenticated production search-results
   provider when it is actually offered, affordable, legally usable and
   compatible with verified private egress.
3. **If obtaining ZDR obstructs stabilization**, do not hold independent
   development or testing hostage to an enterprise contract. Evaluate lawful
   non-ZDR options separately, with explicit retention periods, billing, user
   disclosure, account-query linkability, and compatibility with GoreeCloud's
   privacy promise. A standard plan's data retention is **not ZDR**.
4. **Activation is still a separate decision**: this conditional preference
   does not authorize creating a paid account, adding real keys, sending user
   queries to an account-linked API, changing data-retention promises, removing
   Tor protections, or silently switching the seven approved sources.
   If a non-ZDR option is ultimately recommended, obtain a specific approval
   after presenting the concrete trade-offs and acceptance evidence.

A functioning interface, green CI, and a retained subscriber token cannot
by themselves demonstrate anonymous search or Stable release qualification.
Continue to record actual provider access and production security as separate
open acceptance gates.

## Offline evidence coverage gate

The source-only `scripts/provider_qualification_gate.py` accepts sanitized
JSON documents emitted by the existing opt-in local provider-health probe.
It reads only supplied local files, **never** makes provider requests, and
checks exact one-to-one coverage of the 24 approved provider/category pairs.

```bash
# No files and no outbound request: exits 64
python scripts/provider_qualification_gate.py

# Future ONLY: after independent provider authorization and privacy-staging
# safeguards, collect one bounded, synthetic, already-approved report per
# category using the existing controlled loopback probe. Never run this by
# default and do not pass real searches.
python scripts/provider_qualification_gate.py reports/web.json reports/images.json reports/videos.json reports/news.json
```

A missing/failed pair exits 1; invalid or extra fields, inconsistent counts,
duplicate combinations, malformed categories and unsafe diagnostic content
exit 2; zero reports exits 64. A structurally complete set of 24 reported
`results_observed` outcomes exits 0, but always emits
`"release_qualified": false`. **Anyone can fabricate JSON**: a passing
coverage check is neither cryptographic evidence of authentic provider
responses nor proof of network privacy, contractual rights or Stable readiness.
Keep separate signed/pinned operational evidence, source image IDs, environment
logs (sanitized), independent network isolation and rollback acceptance.

Until supported access is negotiated/verified, do not rerun known 403/429
providers or seek circumvention. The paragraph above describing the October 20
probe is historical: a later private Development cutover to the free Working
preset is separately verified in `FREE-WORKING-SOURCES-CUTOVER.md`. That cutover
did **not** qualify public launch, native fusion or Stable release.
