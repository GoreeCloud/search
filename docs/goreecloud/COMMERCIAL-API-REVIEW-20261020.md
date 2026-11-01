# GoreeCloud Search — Commercial search API due diligence

**Reviewed October 20, 2026. Status: Research and staging only. No commercial plan, credentials, paid requests, user-query disclosure, or live cutover authorized.**

## Existing engineering baseline

GoreeCloud/search currently ships an inactive `searx/engines/braveapi.py` adapter in upstream SearXNG. Its official Web API request uses POST with a JSON body and fixed official endpoint; response validation and regression tests exist. The default engine is `inactive: true` with no API credential. GoreeCloud's private provider profile explicitly excludes `braveapi`; the seven approved families and original provider labels remain unchanged. These safeguards must not be relaxed merely because a user has authorized exploring commercial terms.

The current private Development instance still uses an older image. The next private ingress candidate at draft PR #61 passed isolated synthetic tests, not commercial provider qualification. No proof yet establishes that an authenticated API request succeeds through Tor from this VPS.

## Published options (vendor pricing, not a negotiated quote)

| Provider | Published base price | Query retention | Contractual / integration limitations |
| --- | --- | --- | --- |
| Brave Search API | USD $5 per 1,000 Search requests, with USD $5 in monthly credits. Prepaid credits apply; all plans require payment information. | API query records retained up to 90 days on standard plans; Enterprise ZDR available subject to terms. | Official API supports search applications but restricts persistent caching, redistribution, usage that replicates the API, and unapproved processing. Clarify compatibility with a privacy-oriented metasearch experience and end-user results display before use. |
| Mojeek Search API | GBP £2 per 1,000 Startup requests; GBP £3 per 1,000 Business requests, excluding taxes. | States standard 90-day retention; ZDR by request/custom terms. | Terms and authorized federation, Tor-exit API reachability, result reuse and invoicing must be confirmed. It is not among GoreeCloud's existing seven approved provider families; adding it requires a separate source-choice decision. |
| Exa Search API | From USD $4 per 1,000 instant requests (other modes higher; result-count add-ons). | Enterprise ZDR available; consumer/developer exact term unverified. | Primarily agent/research search; suitability for an end-user web SERP and contractual display permissions require review. |

**Source references, retrieved 2026-10-20:**

- Brave pricing: https://api-dashboard.search.brave.com/documentation/pricing
- Brave API customer privacy: https://api-dashboard.search.brave.com/documentation/resources/privacy-notice (updated 2026-08-25)
- Brave Terms: https://api-dashboard.search.brave.com/documentation/resources/terms-of-service (updated 2026-09-01)
- Brave authenticated Web POST: https://api-dashboard.search.brave.com/api-reference/web/search/post
- Brave API retention and limits: https://api-dashboard.search.brave.com/documentation/resources/help-feedback
- Mojeek API pricing and retention: https://www.mojeek.de/services/search/web-search-api/
- Exa API pricing: https://exa.ai/pricing

## Preferred path: existing approved Brave provider, pending due diligence

Brave is the lowest-friction *technical* candidate because it is already one of the seven approved brand/provider families and has an existing dormant official-API adapter. The user authorized pursuing a commercial provider even without ZDR, subject to price, retention and privacy review **before activation**. This does not approve a paid account, a license agreement, billing, credentials, actual API requests or automatic provider replacement.

Open contractual questions: Does Brave explicitly authorize GoreeCloud's user-facing metasearch experience (including user-selectable Brave result sourcing, result display with attribution and no persistent cache), considering the Terms' functionality-replication restriction? Is Tor-exit API use permitted and supported? Are requests handled via the fixed POST endpoint with results returned under the selected plan? Can account identifiers and raw search terms be separated from individual users; what precise IP/token/access logs, query log retention, subprocessor, territorial and legal-disclosure terms apply? Which ZDR plan and fee can be quoted, and what are the contractual differences from standard 90-day retention? Do the public free monthly credits require payment details? Can hard usage ceilings and disabled auto-reload be configured?

## Implementation and privacy acceptance gates

1. Review vendor's written product permission, customer terms, data-processing terms, published price and any quotation. Do not mistake normal Brave Search privacy for Brave **API customer** retention.
2. Owner reviews actual pricing, required payment method, 90-day query retention (or signed enterprise ZDR terms), account correlation, processor geography, logging and visible end-user privacy disclosure, and separately authorizes any billable activation.
3. Store any approved credentials only in a protected runtime secret outside Git, never in `settings.yml`, CLI output, issues or logs. Keep the default adapter disabled and excluded from all provider selections until that review is complete. No silent fallback from the existing seven providers.
4. Require server-side explicit provider selection/consent, strict budget/quota controls, per-user request limiter, no silent retries after rate limit or CAPTCHA, fixed approved endpoint, HTTPS-only via SOCKS5H, no redirects, POST request body only, and no query/response persistence.
5. Test synthetic local responses and 401/403/429/malformed/timeout failures; then, only following activation approval, perform a bounded authorized real-query smoke using nonpersonal synthetic search terms, separately verify Tor routing and provider acceptance, and halt on access denial.
6. Confirm real search results repeatably across approved use cases and user-visible attribution. Independently complete deployment provenance, production ingress/limiter, fail-closed network, privacy/legal, staging rollback, and production recovery gates before Stable.

**Do not label GoreeCloud Search Stable based on pricing availability, code existence, green tests, the Search readiness endpoint, or a commercial API agreement alone.**
