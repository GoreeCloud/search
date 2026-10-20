# GoreeCloud Search — approved-provider access and release-evidence decision

**Reviewed:** 2026-10-20
**Environment:** seven-provider Development, *not* deployed; live VPS unchanged
**Decision:** provider-results reliability NOT QUALIFIED; keep issues #26, #21 and #1 OPEN

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
2. The provider works through the isolated Tor/SOCKS5H path with verified
   circuit use and a non-leaky resolver, firewall-enforced DNS/metadata/IPv6
   isolation and fail-closed checks. Do not replace Tor with clear/direct egress.
3. Decide whether an account-bound API key is acceptable to GoreeCloud's
   anonymity promise. Tor may hide the server IP while the token still links
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
providers or seek circumvention. The existing public/live Search VPS remains
on its older Development image; no Stable release or user-traffic cutover.
