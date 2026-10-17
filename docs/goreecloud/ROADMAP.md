# GoreeCloud Search — capability delivery map

The supplied GoreeCloud Search feature catalog is a **proposed product target**, not an inventory of shipped features. Current lifecycle: Development.

| Workstream | Current foundation | Open and gated work |
| --- | --- | --- |
| Web search | Three allowlisted provider families: Brave Search, Startpage and Qwant, selected by default with SafeSearch None. Category-specific adapters support Web, Images, Videos and News; Videos excludes Startpage. Synthetic tests verify selection independently of network availability. In the October 16–17, 2026 laptop live check, Startpage returned 10 Web, 50 Image and 8 News results for a public test query; Brave Web returned HTTP 429 and Qwant Web/Images reported access denied. Three-provider Web fusion still returned 10 Startpage results. See [live provider qualification](LIVE-PROVIDER-QUALIFICATION-20261016.md). These one-time observations are not uptime guarantees. | Qualify live egress and per-provider blocks/denials, relevance, ranking and privacy before public use; do not add other providers without governed approval. |
| Search operators | POST-based Web/Images/Videos/News tabs, Settings-managed provider choices, source-specific follow-ups, failure explanations and retries, private no-network preview API, query/bang validation, preserved POST pagination/filter context, 512-character limit and at most three provider families per request. Homepage omits provider-picker buttons and preview shortcut. | Confirm real network behavior, keyboard and assistive-technology acceptance, category consistency and provider selection at release candidate. |
| Privacy | POST, image proxy and private profile | Public rate limiting, formal Privacy Shield/Wardveil integration, disclosure audits |
| Local Index | None in SearXNG imported runtime | Index contract adapter and cycle-safe routing, independent index operation |
| Glaze / owner mockup | Implemented owner-approved responsive Search homepage treatment (cyan mark, cobalt branding, centered search, privacy principles, header/footer and session light/dark toggle) on the existing partial Glaze CSS foundation | Exact rendered visual comparison and official Glaze/a11y/device consumer acceptance; not yet conformance-registered |
| API | SearXNG loopback-only JSON and selected-source attribution for the allowlisted Brave/Startpage/Qwant adapters (not proof of provider contact). | Authenticated, rate-limited versioned GoreeCloud API and independently verified provider audit contracts. |
| AI/research | No GoreeCloud AI layer | Source-grounded answers, citations, conversational research and safety |
| Maps/local/commerce | No independent Maps, local business or commerce index; allowlisted Brave, Startpage and Qwant results are web/media search adapters, not structured local-data services. | Licensed structured integrations require separate approved contracts. |
| Saved search/alerts | Not implemented | Opt-in local-first storage, retention, scheduling and notifications |
| Operations | Loopback-only source runtime, liveness and provider-processor startup readiness (not live network health), source/runtime and Chrome CI | Authenticated public diagnostics, hardening, live source health, independent monitoring, rollout and rollback tests |

Source presence, a compile check or a green CI build does not confer production eligibility, independent-index capability or Glaze conformance.
