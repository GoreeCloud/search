# GoreeCloud Search — mandatory private egress

**Lifecycle: Development.** Effective source candidate: draft PR #18. This is a
privacy-control implementation, **not proof of complete anonymity**.

## Mandatory behavior

The GoreeCloud private Development profile uses
`goreecloud.require_anonymous_egress: true` and a single `outgoing.proxies.all://`
gateway: `socks5h://127.0.0.1:9050`. **Every outbound SearXNG network
client**, including the Brave, Startpage, Qwant and image-proxy clients, must
have a validated local SOCKS5H gateway. SOCKS5H requests DNS resolution through
the gateway rather than the user's DNS resolver. No HTTPS or HTTP direct
fallback is permitted if a gateway is missing, closed, malformed, or rejected.

All registered networks inherit this requirement, even if an engine specifies
its own network override. The network layer rejects external proxy addresses,
non-SOCKS5H protocols, plaintext HTTP targets, disabled TLS verification,
per-request proxy/interface overrides and custom cURL settings. Incoming
cookies are **not passed** to search providers, and common identity-carrying
headers including `Forwarded`, `X-Forwarded-For`, `X-Real-IP`,
`Authorization` and `Cookie` are removed. Query-bearing upstream URL
logging was separately disabled; the remaining exception and telemetry paths
still need a comprehensive privacy review.

If the local SOCKS5H gateway is not running, the user can open the private
homepage and preview source selection, but external provider searches will
fail with provider errors and **no direct egress**. This failure is the
deliberate privacy default, not a reason to bypass the gateway.

## Critical difference: proxy masking versus anonymity

A SOCKS5H protocol and a loopback listener alone do **not** prove that the proxy is
Tor, that the exit IP is shared, that the provider cannot correlate searches,
or that queries are end-to-end anonymous. The application now additionally requires `using_tor_proxy: true` and performs a Tor-exit check through the configured gateway before allocating an outbound provider session. The operator must **also** independently verify that the listening service is genuine Tor and conduct exit-IP, DNS-leak and traffic-isolation checks before claiming any anonymity. A
malicious/misconfigured proxy, upstream network observer, or Tor exit can
still observe metadata; a search provider receives the **plaintext query**
over its HTTPS endpoint and can correlate query content and timing. Search
terms are not blindly randomized because changing their meaning is not a
reliable anonymity measure.

There is **no Tor service listening on 127.0.0.1:9050 on the tested laptop**
at the October 2026 development checkpoint. Actual successful provider
responses over a verified Tor circuit, resistance to traffic correlation,
public service requests, DNS leak tests, user/session isolation, and
end-user browser privacy remain unverified. This source change is **not a
working anonymous-search deployment yet**.

Following result links leaves the Search service and can reveal the user's
network identity to the destination site unless browser-side protections
are used. The inherited image proxy follows the same mandatory egress rule,
but external result URLs and third-party embeds require further auditing.

## Release gates

1. Provision and independently verify a trusted local SOCKS5H privacy gateway
   in a properly isolated Development/Staging environment; do not assume
   binding a socket on port 9050 makes the gateway trustworthy.
2. Verify actual HTTPS provider request delivery through the gateway and
   **no direct traffic** when gateway connections fail, time out, or are
   interrupted. Include DNS resolution and image-proxy requests.
3. Validate search functionality and provider anti-abuse response when
   cookies are suppressed, especially Startpage challenges and Qwant
   DataDome. Never bypass anti-bot/access restrictions or silently reroute
   to disallowed providers.
4. Complete query/URL logging, browser link leakage, exception handling,
   response caching, privacy-retention and session isolation reviews.
5. Integrate GoreeCloud Identity/Privacy Shield and audited public
   authentication and rate limiting, then staging performance and rollback.

### Bounded evidence

At this Development checkpoint, **seven anonymous egress regression cases**
passed on the laptop: allowlist/denylist proxy parsing, no client creation
without a valid relay, strict cURL/TLS/HTTPS guards, identity header and
cookie stripping, and all registered network adapters inheriting the policy.
The local GoreeCloud suite passed **152/152** cases. An actual local Search
POST while the proxy was absent returned an error and no results; every
registered network (15/15) reported private egress enforcement. A private
Granian no-provider listener smoke passed. Those checks do not establish
production readiness or a functioning Tor relay.

Any previously recorded real-provider results (e.g. Startpage Web/Images/News
during the October 16–17 live-provider investigation) were captured **before**
this mandatory privacy-relay change and must not be presented as proof of
anonymous searches.
