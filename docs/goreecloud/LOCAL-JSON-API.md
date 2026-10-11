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
    "safesearch": 1,
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
    "selected_engines": ["brave", "startpage"],
    "selected_engine_count": 2,
    "selection_not_contact_confirmation": true,
    "represented_engines": [],
    "represented_result_counts": {},
    "representation_not_contact_confirmation": true
  }
}
```

This is an illustrative shape, not a fabricated live-search response. SearXNG's original keys and result serialization remain unchanged; the private extension filters out primary result links that are not well-formed HTTP(S) destinations, while upstream callers not requesting the extension continue to receive the upstream response shape and result population. The selected list reflects engine selection after query parsing, not contacted, completed or successful providers. `represented_engines` and `represented_result_counts` describe selected engine labels attached to the safe primary results actually returned on this page. A merged result tagged by multiple engines contributes once to each represented engine, so counts can overlap. These labels are attribution attached to result objects, not independently verified provider identity, network completion, response authenticity, or total provider requests. Empty results produce an empty attribution map.

Private-profile limits: at most 512 raw submitted query characters and **exactly two permitted built-in engines**, `brave` (Brave Search, used by Brave Browser) and `startpage`. Only one or both can be selected; every other engine is rejected before provider dispatch. The fanout cap is 2. Oversized queries return HTTP 413; unsupported explicit engines, provider bangs or automatic external-navigation requests return 422, and URL-query submission returns 405. Rejected JSON searches return a structured privacy policy error without echoing query terms. Unexpected upstream plugin redirects are also denied. Private responses are uncached (`Cache-Control: private, no-store, max-age=0`) and set `Referrer-Policy: no-referrer`.

**Not included:** public authentication, OAuth, quotas, versioned API stability, audited upstream provider identity, Privacy Shield consent, or Wardveil admission. Those require independently governed contracts and security acceptance before network exposure.
