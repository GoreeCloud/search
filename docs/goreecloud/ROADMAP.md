# GoreeCloud Search — capability delivery map

**Owner vision, October 23, 2026:** GoreeCloud Search is to become an
independently branded and operated, **self-hosted, native metasearch platform**.
Its own frontend, API, provider orchestration, fusion/ranking, data, cache,
security, administration and deployment shall be under GoreeCloud control.
Google, Bing, Brave and later sources are **external indexes**, not hosted by
GoreeCloud, and must be legally/contractually qualified individually.
One query should produce **one ranked results experience**, not separate
Google/Bing/Brave feeds or a required provider picker. The primary navigation
will support Web, Images, Videos, News, Shopping, Maps and More *as each
category is genuinely implemented and qualified*; do not render unwired
categories as functioning features. Real Linux/Windows/Android/iOS/iPadOS
applications require OS-native builds in addition to the responsive website.
GoreeCloud UI (GC UI) governs every applicable surface.

The table below is a Development inventory, **not** an inventory of shipped
features or a promise of provider permission. Current environment: private
Development; the exact official release-lifecycle stage remains unqualified.
See [source baseline and Anchor gates](SOURCE-BASELINE-QUALIFICATION.md) and
the [native fusion integration contract](FUSION-ENGINE-CONTRACT.md).

| Workstream | Current foundation | Open and gated work |
| --- | --- | --- |
| Web search | Legacy SearXNG-derived seven-family allowlist: **Brave, Startpage, Qwant, DuckDuckGo, Ecosia, Bing and Google**. `All Sources` configures these Web adapters but does not prove access, permissions or relevance. The current `Working` deployment preset selects DuckDuckGo/Bing/Startpage Web. Synthetic tests verify selection, not live coverage. | Own GoreeCloud orchestration and unified ranking, then qualify real provider access/licensing, denials, relevance, egress and privacy before public use. |
| Search operators | POST-based Web/Images/Videos/News tabs, Settings-managed source choices, follow-ups, failure explanations and retries, private no-network preview API, query/bang validation and preserved POST pagination/filter context. `Working` Images currently uses **Bing only**, not multi-index fusion. | Make source choices optional diagnostics/advanced preferences while auto-federating **only permitted and verified** sources; validate category, touch, keyboard, assistive technology and error behaviors. |
| Privacy | POST, image proxy and private profile | Public rate limiting, formal Privacy Shield/Wardveil integration, disclosure audits |
| Local Index | GoreeCloud-owned opt-in SQLite FTS5 corpus and a separate Linux service candidate; neither is a general Internet index or automatically blended with provider results. | Securely combine opted-in approved local content with permitted external results using an independently qualified fusion contract. |
| GoreeCloud UI (GC UI) / owner mockup | The current Search web interface is a **legacy Glaze consumer**, not a GC UI-conformant implementation. Its existing responsive treatment and synthetic browser checks remain functional Development evidence only. The active dependencies are recorded in [the migration inventory](GC-UI-CONSUMER-MIGRATION.md). | Replace the retired styling contract with supported GC UI Foundations and a Search-specific accessible experience; compare owner screenshots, verify across devices, then separately qualify integration and release. |
| API | SearXNG loopback-only JSON and selected-source attribution for the seven allowlisted provider families (not proof of provider contact). | Authenticated, rate-limited versioned GoreeCloud API and independently verified provider audit contracts. |
| AI/research | No GoreeCloud AI layer | Source-grounded answers, citations, conversational research and safety |
| Maps/local/commerce | No Maps/local business or Shopping vertical; allowlisted upstream adapters are Web/media rather than structured local/commerce data. | License and test structured source contracts, geodata rights, business/product identity and safe geographic/category UX before activating tabs. |
| Saved search/alerts | Not implemented | Opt-in local-first storage, retention, scheduling and notifications |
| Operations | Loopback-only source runtime, liveness and provider-processor startup readiness (not live network health), source/runtime and Chrome CI | Authenticated public diagnostics, hardening, live source health, independent monitoring, rollout and rollback tests |

Source presence, a compile check or a green CI build does not confer production eligibility, independent-index capability or GC UI conformance.

## New parallel priorities — dependent release gates

1. **P0 source rights and privacy:** Google Custom Search JSON API is closed
   to new customers and sunsets January 1, 2027; Microsoft retired standalone
   Bing Search APIs in August 2025; Brave Search API restricts cache/derivative
   uses. Do not assume an authorized triple-provider raw-result feed. Review
   contractual ability to aggregate/rerank/display and source disclosures
   before paid activation or real-data use. [Google](https://developers.google.com/custom-search/v1/overview) ·
   [Microsoft](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement) ·
   [Brave terms](https://api-dashboard.search.brave.com/documentation/resources/terms-of-service).
2. **P0 owned fusion:** Implement typed source/vertical contracts, per-provider
   single-vote reciprocal-rank fusion, URL/media dedup, safe canonicalization,
   scoring tests and bounded failure handling. `native_search/fusion.py` is the
   **offline, synthetic-only first milestone**, not a wired runtime.
3. **P1 real search quality:** Record reproducible missing-result, duplicate,
   relevance, image/video identity, provider-denial and latency benchmarks;
   qualify any provider individually rather than hiding zero-result failure.
4. **P1 native GC UI and self-hosted production boundary:** One clean ranked
   results view, useful category-specific cards and accessibility; separately
   build own query/orchestrator API, configuration database, cache within
   license limits, rate limiter, protected credentials and admin diagnostics.
5. **P2/P3 expansion:** Add licensed Shopping/Maps, news story clustering,
   own crawler and independent index incrementally. Robots/rights/takedown,
   recovery, multi-OS acceptance and Seal/Anchor gates remain mandatory.

Workstreams may advance concurrently, but source approvals and network/security
evidence remain **activation blockers**. Preserve private `search-dev.goreecloud.com`;
do not change public `search.goreecloud.com` until its independent gates pass.
