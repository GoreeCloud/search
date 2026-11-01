# GoreeCloud Search — provider DNS answer pinning candidate

**Status:** Local source-only security candidate, 2026-10-23. Not deployed, not an egress-firewall acceptance, not Public or Anchor readiness.

## Boundary and implementation

The free-first Development profile sets `goreecloud.private_search: true` but deliberately does not require the Tor relay. Its provider transport already rejects unsafe HTTPS URL syntax, IP-literal/local names, untrusted per-request transport overrides, automatic redirects, cookies and identifying headers, and HTTP/3. Those controls alone did **not** prevent a syntactically valid provider hostname from changing DNS answers to a private or loopback address between URL validation and connection.

The guarded direct-HTTPS path now:

1. Validates the provider URL and request overrides before any DNS request.
2. Resolves the destination hostname through the runtime resolver once per request (3-second timeout). Empty, malformed, overly large (more than 16 unique), mixed public/private, loopback, link-local, special/reserved and IPv4-translation IPv6 answers fail before a provider client is created. NAT64 prefixes `64:ff9b::/96` (RFC 6052) and `64:ff9b:1::/48` (RFC 8215) are denied explicitly because an IPv6 `is_global` result can encapsulate a private IPv4 destination.
3. Supplies every vetted result to libcurl's `CURLOPT_RESOLVE` for the *exact host:443*; this pins the actual connection while retaining the original HTTPS hostname for SNI and certificate validation. The option is not a separate, unbound preflight DNS check. `CURLOPT_PROXY=""` disables environment-based HTTPS/ALL proxy fallback for the direct profile, and HTTP/3 remains disabled.
4. Refuses unpinned guarded direct clients and direct guarded clients configured with a proxy. The separate anonymous/Tor profile continues to delegate DNS to its locally validated SOCKS5H relay with per-client Tor attestation; it does not perform local direct DNS pinning.

Official transport semantics: [libcurl `CURLOPT_RESOLVE`](https://curl.se/libcurl/c/CURLOPT_RESOLVE.html) and [`CURLOPT_PROXY`](https://curl.se/libcurl/c/CURLOPT_PROXY.html). No libcurl `CURLOPT_PREREQFUNCTION` callback is implied.

## Distinct public/private host contract

The source-controlled Caddy snippet for `search-dev.goreecloud.com` retains the NetBird `100.64.0.0/10` remote-IP matcher and explicit HTTP 403 fallback; the private app accepts that exact host behind separate authenticated private ingress and rejects `search.goreecloud.com` as a private Host header. This is a static/source contract, **not proof of the live Caddy configuration or NetBird policy**. The owner intends `search.goreecloud.com` to be public in a separate governed release and every `*-dev.goreecloud.com` app to remain private by default. The Search repository cannot independently certify that whole DNS namespace or other applications.

## Evidence and still-open gates

- New `tests/goreecloud/test_provider_dns_answer_pin.py` covers curl resolver options, DNS answer families, mixed answers, failure-before-client, no proxy fallback and IPv6 formatting, using synthetic DNS responses and no remote provider requests. A separate local transport fixture was **executed with socket permission**: an unresolvable hostname mapped through the installed curl transport's `CURLOPT_RESOLVE` reached the intentionally TLS-less loopback listener, and the expected TLS failure prevented any completed HTTPS exchange. This supports actual option operation, not full malicious-DNS acceptance.
- `tests/goreecloud/test_search_hostname_boundary.py` covers the source-controlled dev Caddy ACL and private app/public host distinction.
- Existing guarded transport/anonymous egress and full exact-head CI must be rerun after integration. On this execution host, the preexisting `test_real_free_profile_initializes_all_networks_with_guard` exits with a 3-second `done()` future timeout **on both untouched base and this candidate**; treat that separately as an initializer test-environment issue, not a passing gate.
- **Open:** end-to-end adversarial DNS rebinding and post-reconnect socket-peer checks with a controlled resolver/fixture in a disposable network namespace; production Linux-vs-container resolver behavior; DNS query volume/latency and concurrent connection-pool behavior; real egress firewall enforcing destination IP/port including IPv6 and UDP; browser/private-ingress external denial, authentication, TLS/NetBird ACL/route testing; immutable source-to-image digest provenance; sustained provider availability and rollback.
- Before promotion, rebase/apply on the exact current GoreeCloud `feature/search-working-free-sources-20261020` head, run relevant unit/integration/CI and disposable image smoke, perform a reviewed egress/SSRF test against a controlled DNS rebinding fixture, and separately verify the private Development endpoint from both NetBird and non-NetBird clients. None of these future release gates are satisfied merely by this source candidate.
