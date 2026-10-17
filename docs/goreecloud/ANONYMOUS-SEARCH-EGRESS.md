# GoreeCloud Search — anonymous-egress development policy

**Lifecycle: Development.** This is a **fail-closed transport requirement**, not a certification of absolute anonymity.

## User protection contract

Every outgoing private Search provider request must be made through a locally hosted, independently verified **Tor SOCKS5h** relay. Without an available Tor service or on Tor verification failure, **no direct provider fallback is permitted**. This extends to the Search application's shared outbound network client, specialized engine networks, result-image proxy, and ordinary engine metadata requests that use the same outbound client. The `socks5h` scheme requests proxy-side DNS resolution rather than exposing upstream names to host DNS.

The private configuration uses `socks5h://127.0.0.1:9050` with `outgoing.using_tor_proxy: true`. The service is **not bundled**; operators must separately provision a legitimate local Tor relay, verify it is operating and enforce network/firewall egress policies. The application uses SearXNG's existing Tor exit check, which queries the Tor Project through the configured proxy, before ordinary provider requests. An unavailable relay blocks provider traffic; changing this configuration to direct networking is **not an acceptable production workaround**.

The `require_anonymous_egress` setting in the GoreeCloud private profile is enabled by default. The `Network.get_client` path requires Tor verification on named networks, and `new_client` rejects outbound clients missing a single numeric-loopback `socks5h` route, including HTTP proxies, `socks5` with local DNS, mixed direct routes, remote proxy hostnames and secret-bearing proxy URLs. The change is deliberately limited to the GoreeCloud private profile, not all upstream SearXNG deployments.

## What this does *not* guarantee

- A search provider receives the actual search terms and can infer identifying information from query content, timing or context. Do **not** append random words or silently alter the query to pretend to provide anonymity; it would affect correctness and may make queries **more** linkable.
- Anonymity depends on a trusted, correctly configured local Tor service, a genuine Tor exit, absent direct network bypasses, and the applications' request handling. Tor can be blocked or rate-limited by providers. Browser visits to external search results are a separate connection, **not** automatically protected by this server's Tor routing.
- Cookies, upstream relay/service behavior, Tor stream/circuit isolation, logging/retention, external asset access, JavaScript, browser extensions, and user/device fingerprinting require their own audits. The shared Search service may reuse transport identity/circuits across user requests. No per-user unlinkability, unlinkable query isolation, end-to-end anonymity or production privacy certification is claimed.
- Tor's network masking protects the Search host's direct network address from providers, but its exit address is visible. Operators must not falsely advertise that a search term itself is encrypted from the destination provider (HTTPS encrypts transport to the provider, not against the provider).

## Expected development behavior

As of October 17, 2026 the development laptop had **no installed Tor executable or listener** on the conventional SOCKS ports. With this change, ordinary live provider searches on that laptop cannot be presumed to work and **should fail closed** until the relay is provisioned. This replaces the earlier, functionally successful but directly connected provider checks. Do not reduce the privacy policy to restore the old results.

Regression tests cover accepted/rejected relay URIs, Tor-verification enforcement, and refusal to allocate a direct HTTP transport. CI's no-provider unit/browser/private-Granian checks do not establish a real Tor circuit or working provider access. Required next gates: test with a real Tor service and verify provider-visible exit versus host IP without exposing sensitive data; audit all outbound code paths and DNS/firewall leak protection; add user-facing service-unavailable indications if Tor is offline; test isolation, latency, provider access denials, browser result navigation disclosures, cookies and metadata; qualify public authentication, rate limits, logging retention, restart and rollback.

**Do not merge or deploy this security branch as Stable based on static or synthetic CI alone.**
