# GoreeCloud Search — capability delivery map

The supplied GoreeCloud Search feature catalog is a **proposed product target**, not an inventory of shipped features. Current lifecycle: Development.

| Workstream | Current foundation | Open and gated work |
| --- | --- | --- |
| Web search | Exactly two built-in options: Brave Search (`brave`) and Startpage (`startpage`), enabled in the private runtime; all other upstream providers excluded | Independent real-provider availability, Startpage proof-of-work challenge handling, ranking and result-quality evaluation, no expansion to other built-in providers |
| Search operators | SearXNG syntax and preferences; private provider preflight, direct Both/Brave/Startpage POST switching, one-source refinement and exact provider persistence through pagination | GoreeCloud ranking profiles, advanced policy filters and audited provider explanations |
| Privacy | POST, image proxy and private profile | Public rate limiting, formal Privacy Shield/Wardveil integration, disclosure audits |
| Local Index | None in SearXNG imported runtime | Index contract adapter and cycle-safe routing, independent index operation |
| Glaze | Local stable CSS foundation and app-specific mapping | Runtime integration, accessibility, device/rendered acceptance, conformance registration |
| API | SearXNG JSON with exact two-provider selected-source metadata (not provider-contact proof) | Authenticated versioned GoreeCloud API, quotas, stable schemas and verified source-proof metadata |
| AI/research | No GoreeCloud AI layer | Source-grounded answers, citations, conversational research and safety |
| Maps/local/commerce | No additional built-in engines; only Brave Search and Startpage web-result capabilities | Licensed structured integrations require separate approved platform contracts without adding selectable search providers |
| Saved search/alerts | Not implemented | Opt-in local-first storage, retention, scheduling and notifications |
| Operations | Loopback-only source runtime, liveness and provider-processor startup readiness (not live network health), source/runtime and Chrome CI | Authenticated public diagnostics, hardening, live source health, independent monitoring, rollout and rollback tests |

Source presence, a compile check or a green CI build does not confer production eligibility, independent-index capability or Glaze conformance.
