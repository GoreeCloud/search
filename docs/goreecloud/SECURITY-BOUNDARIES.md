# GoreeCloud Search security and authority boundaries

**Development. No operational security or Production acceptance granted.**

1. The supplied wrapper `scripts/run-private.sh` requires a 32+-character secret and refuses public-interface, public-instance, GET, and unproxied-image overrides. It selects the loopback-only configuration.
2. JSON in the local profile is **not authenticated**. Never expose this profile to untrusted networks. A public GoreeCloud API needs separately verified Identity, Privacy Shield authority and API limits.
3. SearXNG transmits queries to configured search providers under their own policies. The source does not guarantee provider privacy or independent indexing.
4. Before public deployment, independently validate SSRF/XSS protections, rate limiting/Valkey, HTTPS and reverse proxies, secret management, query redaction, logging/retention, uptime, rollbacks and live security/privacy gates.
5. Glaze is presentation-only: it must not imply consent, permission, authorized indexing, Identity state, Wardveil rules, or Production approval.
6. The private mode rejects external bangs and first-result navigation before provider dispatch; unexpected redirects are denied after a search. Explicit user clicks on result links can still disclose information to destinations.
7. Raw query length is checked before parsing operators. The submitted search remains POST-only, with selection caps before network dispatch. Private mode returns uncached 404 responses for direct `/opensearch.xml` and `/autocompleter` GET endpoints, blocking alternate browser-discovery and suggestion routes even if a client bypasses the interface.
8. Private mode rejects serialized GET/POST preference imports before decoding; upstream normally auto-applies shared settings links, which can silently change which providers a user searches. Ordinary local Preferences forms remain available and uncached. Private navigation never copies shared preference tokens into links.
9. Main clickable search results use a bounded HTTP(S) URL-scheme and authority guard in private HTML and JSON. This does not constitute complete safety validation of result template secondary links, embedded media, image proxies, outbound HTTP requests or the sites users choose to visit.
10. The represented-source display counts selected engine names carried on accepted primary result objects for this page only. It does not authenticate the provider, establish that an HTTP request succeeded, measure request volume, or cover discarded unsafe results, answers or infoboxes. This is a transparent result-label inventory, not a provider audit.
11. Inherited upstream CI/release automation remains disabled. Bounded source/runtime and synthetic browser tests are not Production or official Glaze acceptance.
