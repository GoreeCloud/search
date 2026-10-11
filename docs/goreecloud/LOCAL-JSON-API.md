# GoreeCloud Search — local JSON extension

**Lifecycle:** Development. **Exposure:** loopback only. **Authentication:** none; this interface must not be published on a network.

The private profile enables SearXNG's inherited JSON search response through `POST /search` with `q` and `format=json` in the request body. GET with search terms is rejected. Running an actual search transmits the terms to the enabled upstream search providers; the source-selection metadata is not an assertion that any provider received or answered a request.

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
    "selected_engines": ["Engine A", "Engine B"],
    "selected_engine_count": 2,
    "selection_not_contact_confirmation": true
  }
}
```

This is an illustrative shape, not a fabricated live-search response. SearXNG's original keys and result serialization remain unchanged; upstream callers not requesting the GoreeCloud extension continue to receive their original response format. The selected list reflects the engine selection after query parsing, not contacted, completed or successful providers.

Private-profile limits: at most 512 raw submitted query characters and 32 distinct selected engines. Oversized queries return HTTP 413, excessive engine selection or automatic external-navigation requests return 422, and URL-query submission returns 405. Rejected JSON searches return a structured privacy policy error without echoing query terms. Unexpected upstream plugin redirects are also denied. Private responses are uncached (`Cache-Control: private, no-store, max-age=0`) and set `Referrer-Policy: no-referrer`.

**Not included:** public authentication, OAuth, quotas, versioned API stability, audited upstream provider identity, Privacy Shield consent, or Wardveil admission. Those require independently governed contracts and security acceptance before network exposure.
