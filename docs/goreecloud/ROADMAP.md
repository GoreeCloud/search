# GoreeCloud Search — capability delivery map

The supplied GoreeCloud Search feature catalog is a **proposed product target**, not an inventory of shipped features. Current lifecycle: Development.

| Workstream | Current foundation | Open and gated work |
| --- | --- | --- |
| Web/multimedia/news | SearXNG provider ecosystem and federated aggregation | Provider qualification, ranking tuning, result quality evaluation |
| Search operators | SearXNG syntax and preferences; private provider preflight with opt-in one-source search and result-page POST refinements | GoreeCloud ranking profiles, advanced policy filters and audited provider explanations |
| Privacy | POST, image proxy and private profile | Public rate limiting, formal Privacy Shield/Wardveil integration, disclosure audits |
| Local Index | None in SearXNG imported runtime | Index contract adapter and cycle-safe routing, independent index operation |
| Glaze | Local stable CSS foundation and app-specific mapping | Runtime integration, accessibility, device/rendered acceptance, conformance registration |
| API | SearXNG JSON with opt-in, local-only selected-source metadata (not provider-contact proof) | Authenticated versioned GoreeCloud API, quotas, stable schemas and verified source-proof metadata |
| AI/research | No GoreeCloud AI layer | Source-grounded answers, citations, conversational research and safety |
| Maps/local/commerce | Upstream search links/adapters where available | Licensed structured data, coordinates, reviews and geographic privacy |
| Saved search/alerts | Not implemented | Opt-in local-first storage, retention, scheduling and notifications |
| Operations | Loopback-only source runtime, liveness and provider-processor startup readiness (not live network health), source/runtime and Chrome CI | Authenticated public diagnostics, hardening, live source health, independent monitoring, rollout and rollback tests |

Source presence, a compile check or a green CI build does not confer production eligibility, independent-index capability or Glaze conformance.
