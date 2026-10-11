# GoreeCloud Search security and authority boundaries

**Development. No operational security or Production acceptance granted.**

1. The supplied wrapper `scripts/run-private.sh` requires a 32+-character secret and refuses public-interface, public-instance, GET, and unproxied-image overrides. It selects the loopback-only configuration.
2. JSON in the local profile is **not authenticated**. Never expose this profile to untrusted networks. A public GoreeCloud API needs separately verified Identity, Privacy Shield authority and API limits.
3. SearXNG transmits queries to configured search providers under their own policies. The source does not guarantee provider privacy or independent indexing.
4. Before public deployment, independently validate SSRF/XSS protections, rate limiting/Valkey, HTTPS and reverse proxies, secret management, query redaction, logging/retention, uptime, rollbacks and live security/privacy gates.
5. Glaze is presentation-only: it must not imply consent, permission, authorized indexing, Identity state, Wardveil rules, or Production approval.
6. The private mode rejects external bangs and first-result navigation before provider dispatch; unexpected redirects are denied after a search. Explicit user clicks on result links can still disclose information to destinations.
7. Raw query length is checked before parsing operators. The submitted search remains POST-only, with selection caps before network dispatch.
8. Inherited upstream CI/release automation remains disabled. Bounded source/runtime and synthetic browser tests are not Production or official Glaze acceptance.
