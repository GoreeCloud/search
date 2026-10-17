# GoreeCloud Search — local JSON extension

**Lifecycle:** Development. **Exposure:** loopback only. **Authentication:** none; this interface must not be published on a network.

The private profile enables SearXNG's inherited JSON search response through `POST /search` with `q` and `format=json` in the request body. GET with search terms is rejected. Running an actual search transmits the terms to the enabled upstream search providers; the source-selection metadata is not an assertion that any provider received or answered a request.

### No-network preview contract

Before searching, `POST /preview` with form-body `q=...&format=json` returns **no query text and no provider requests**. It uses the current SearXNG parser and the same privacy/fanout limits as execution. For example, an empty-source hypothetical response is:

```json
{
  "goreecloud": {
    "mode": "private_search_preview",
    "network_requests_made": false,
    "will_contact_providers_on_continue": false,
    "selected_engines": [],
    "selected_engine_count": 0,
    "selected_categories": [],
    "language": "en",
    "safesearch": 0,
    "time_range": "",
    "page": 1,
    "query_length": 12,
    "selection_not_contact_confirmation": true
  }
}
```

The example is illustrative, not a live query or a guarantee that the same fields predict provider availability. `will_contact_providers_on_continue` indicates only that the plan has selectable providers; actual browser continuation posts a separate request. There is no public API/authentication contract.

### Search execution response

An additive `goreecloud` response object is available when `goreecloud.private_search` is enabled:

```json
{
  "query": "sample",
  "results": [],
  "answers": [],
  "corrections": [],
  "infoboxes": [],
  "suggestions": [],
  "unresponsive_engines": [],
  "goreecloud": {
    "selected_engines": ["brave", "qwant", "startpage"],
    "selected_engine_count": 3,
    "selection_not_contact_confirmation": true,
    "represented_engines": [],
    "represented_result_counts": {},
    "representation_not_contact_confirmation": true
  }
}
```

This is an illustrative shape, not a fabricated live-search response. SearXNG's original keys and result serialization remain unchanged; the private extension filters out primary result links that are not well-formed HTTP(S) destinations, while upstream callers not requesting the extension continue to receive the upstream response shape and result population. The selected list reflects engine selection after query parsing, not contacted, completed or successful providers. `represented_engines` and `represented_result_counts` describe selected engine labels attached to the safe primary results actually returned on this page. A merged result tagged by multiple engines contributes once to each represented engine, so counts can overlap. These labels are attribution attached to result objects, not independently verified provider identity, network completion, response authenticity, or total provider requests. Empty results produce an empty attribution map.

Private-profile limits: at most 512 raw submitted query characters and **three allowlisted provider families**: Brave Search (`brave`), Startpage (`startpage`) and Qwant (`qwant`), plus their specifically configured category variants. The all-sources choice enables three families by default (at most three adapters in a given category; Videos supports Brave and Qwant, not Startpage). Explicit `engines=` form selections take precedence over inherited category selections; otherwise upstream SearXNG can union selections and unexpectedly broaden disclosure. An engine/bang conflict is rejected, never silently expanded. Result-page POST actions preserve validated engine selection through pagination without changing the saved preference. The fanout cap is **3**. Oversized queries return HTTP 413; unsupported explicit engines, provider bangs or automatic external navigation return 422, and URL-query submission returns 405. Rejected JSON searches return privacy policy errors without reflecting query terms. Unexpected redirects are denied. Private responses use `Cache-Control: private, no-store, max-age=0` and `Referrer-Policy: no-referrer`.

**Not included:** public authentication, OAuth, quotas, versioned API stability, audited upstream provider identity, Privacy Shield consent, or Wardveil admission. Those require independently governed contracts and security acceptance before network exposure.
