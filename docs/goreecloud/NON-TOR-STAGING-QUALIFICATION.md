# GoreeCloud Search — non-Tor staging qualification

**Environment:** isolated Development/Staging only; never substitute the running production VPS applications.  
**Product state:** Draft PR #18, not released.  
**Privacy goal:** a search provider sees the remote GoreeCloud Search server's egress IP, not the visitor's IP or browser identity metadata. Search terms remain visible to the selected provider. This is server IP masking, not anonymity.

## Baseline verified on October 17, 2026

- GoreeCloud Search's Development branch supports an explicit `server_masked` mode and non-Tor SOCKS5H/VPN gateways. Tor is not required.
- A clean detached laptop development checkout passed **179/179** GoreeCloud tests at source commit `b17436aded90b9f914c181826d44aa4975788f42`. This includes image URL checks, image redirect refusal, SVG/binary media rejection, and disabled favicon-proxy access.
- A read-only inventory of the shared GoreeCloud VPS showed production Docker applications and infrastructure already running, including Caddy, NetBird and DNS, and **no running GoreeCloud Search container** in the observed list. No Search service, production routing, firewall or public endpoint was created.
- No actual remote visitor-to-search-provider IP masking or DNS-rebinding/metadata-route denial has been demonstrated. No production promotion may be inferred from unit tests or CI.

## Isolated staging architecture

1. Use a dedicated non-production container, service identity, writable data directory, and service-specific bridge/network namespace. Do **not** share the host network, production Caddy configuration, database, credentials, or application directories.
2. Keep the staging HTTP listener bound to loopback or another explicitly authorized private staging interface. Do not publish a public DNS record or change existing 80/443 proxy routes. Enable a separately authorized staging ingress only after authentication, origin/host validation and TLS are qualified.
3. Keep `goreecloud.private_search: true`, POST query transport, no-store, no-referrer, HTTPS-only upstream, full TLS validation and disabled autocomplete/favicons. Preserve the approved Brave Search, Startpage and Qwant source list with no provider fallback.
4. For remote server IP masking, use `configs/goreecloud/server-masked-staging.yml` only after confirming the **server and user are distinct**. Both the profile acknowledgement and `GOREECLOUD_SERVER_MASKED_EGRESS=1` are required. Keep that environment variable unset for local laptop trials.
5. Before allowing outbound media requests, impose **service-specific egress denial** for loopback, RFC1918 and carrier-grade private IPv4, link-local, documentation/reserved ranges, cloud metadata, IPv6 unique-local/link-local and any internal host subnets. Account for IPv4/IPv6, DNS answers changing after lookup, and alternate address encodings. Do not enforce these rules globally on the shared VPS.
6. Use a private resolver path with controlled logging and no visitor-query storage. Container runtime defaults and Docker bridge isolation **do not themselves prove** forbidden destinations are blocked.

## Offline readiness semantics

The private `/healthz` route is a process-liveness indicator, not evidence that
a search can be executed. The `/readyz` route now fails with HTTP 503
(`NOT_READY`) unless at least one selected provider processor is initialized
**and all registered outbound networks** satisfy the private-egress
configuration policy. This catches absent networks, insecure per-engine
settings, invalid SOCKS5H gateways, and hosted modes lacking either opt-in
without creating any network client or disclosing provider configuration.

Brave's upstream engine defaults may request HTTP/3, which the private
transport forbids. Initializing GoreeCloud private networks now explicitly
disables inherited HTTP/3 preferences to prevent false provider failures.
Ordinary upstream SearXNG networks are unchanged.

HTTP 200 (`READY`) means **offline configuration is acceptable only**. It
does not verify that a gateway listener is running, a remote host is
separate from the visitor, a provider is available, or network policy
prevents DNS rebinding. No cached or live search-query evidence may be inferred.
Only independently validated staging tests can confirm these capabilities.

## Private limiter and privacy-safe rate accounting

The Development/Staging profile intentionally leaves `server.limiter: false`
while no isolated Valkey service, trusted ingress, and request-identity controls
are approved. Its `configs/goreecloud/limiter.toml` is an explicit local-only
botdetection configuration, **not** permission to enable a public limiter or
publish the instance. Public or explicitly limiter-enabled readiness now requires
the installed Valkey-backed limiter; `/readyz` returns HTTP 503 otherwise.

Private GoreeCloud limiter logs are reduced to generic decision labels rather
than serialized HTTP forms, search terms, client addresses or client token
values. Its per-client rate counter names use an HMAC-SHA256 of the client
network with the server secret, not a literal IP prefix. The existing link-token
key is already hashed; related private-mode ping logs are also sanitized.
Counter pseudonyms are linkable during the rate-limit period and **not**
anonymity: ingress components and Valkey operators require separate controls.
A strongly random per-instance server secret must be configured; rotating it
resets counter identity. Do not enable unrestricted access from unknown
forwarded-IP headers or allow requests from untrusted Caddy/edge addresses.

Private limiters still need integration qualification with Valkey and
trusted-forwarded-IP handling, expiry verification, provider failure behavior,
legitimate-device traffic and abuse cases. A synthetic unit test cannot prove
that the hosting reverse proxy, Valkey, logs or DNS have zero data retention.

## DNS-pinned SOCKS5H gateway experiment — Development only

This repository now includes a **staging-only** non-Tor TCP SOCKS5H gateway
(`utils/goreecloud_private_socks_gateway.py`) and matching
`configs/goreecloud/dns-pinned-gateway-staging.yml`. They are opt-in
experimental files, **not an installed or running service**. The existing
server-masked and local profiles are unchanged. The staging profile binds the
HTTP server to loopback, sends all HTTPS provider requests to
`socks5h://127.0.0.1:19050` and forbids public ingress and Tor.

Use the gateway **only inside a dedicated remotely hosted Search network
namespace** where both processes share localhost, under a service-specific
egress firewall and trusted private DNS. The gateway's only accepted SOCKS5
command is CONNECT with a DNS hostname on TCP 443; it rejects client-supplied
IP literals, nonstandard ports, private/local names and unauthenticated
methods. The gateway resolves each hostname once, refuses the *entire* DNS
answer if any IPv4 or IPv6 result is not publicly routable, then connects
via a numeric IP socket. It never re-resolves the hostname during connecting.
It does not capture, inspect or log HTTPS queries or hostname/IP details.
Its finite DNS, connect and connection timeouts and small concurrency
allowance limit resource exhaustion.

This closes a **gateway-path DNS-rebinding time-of-check/time-of-use gap**
for the source-resolved address in the tested connection flow. It is **not**
proof that the host has no alternative egress path, that the local resolver
cannot be abused, or that TLS providers only see the remote server address.
A separate scoped firewall must restrict all traffic — including IPv6,
localhost, metadata, internal routing and bypass attempts — from the
Search workload; a container or a loopback gateway alone is insufficient.

### Additional gateway and isolation preflight controls

The DNS-pinned staging gateway also denies selected IPv6 transition/translation
networks (IPv4-mapped, NAT64 well-known/local-use, 6to4, and Teredo). Some
translation/tunnel addresses may appear globally scoped while encapsulating
an otherwise private IPv4 destination. Gateways are limited to 24 active
connections; when all slots are occupied, new connections are closed
immediately rather than queued indefinitely. Synthetic tests verify both
over-capacity rejection and a real bidirectional SOCKS handshake over a
**local** fixture socket without public network traffic.

`utils/goreecloud_staging_isolation_check.py` is a **read-only preflight**
for a future staging container named `goreecloud-search-private-staging`
and custom bridge named `goreecloud-search-staging-egress`. It checks
nonroot identity, no published ports, dropped capabilities, read-only root,
new-privilege denial, resource limits, no host mounts, explicit custom
network separation and an ephemeral teardown. Its Docker inspection stays
in process memory and does not print image environments or credentials.

An acceptable container configuration is **never** proof of actual egress
firewall enforcement. Even with zero configuration violations, the check
returns nonzero `NOT_QUALIFIED` until separate, controlled packet-level
firewall/DNS/metadata and visitor-IP tests are completed. The inspector
does not change the host, Docker bridge, nftables, VPS or running services.
It can be run later in isolated staging with:
`python -m utils.goreecloud_staging_isolation_check`.

### Required staging verification, prior to operation

1. Provision a new isolated *remote* namespace and service account, no
   shared Docker host network and no published port. Do not change production
   host firewall, DNS, Caddy, VPN or Docker networks.
2. Apply and independently validate namespace-specific egress deny rules
   for all forbidden destinations, including private/reserved A+AAAA DNS
   results, link-local, metadata, and mixed/rebinding answers.
3. In that namespace only, start the gateway with
   `python -m utils.goreecloud_private_socks_gateway --port 19050`.
   Configure Search using the matching DNS-pinned staging settings, a
   synthetic per-environment secret, and localhost-only/private ingress.
4. From a separate authorized test client, use only synthetic searches
   and controlled HTTPS endpoints. Capture sanitized destination-IP and
   header evidence to verify both no bypass and server rather than visitor
   source IP. Do not rely on the offline gateway tests as deployment proof.
5. Close the staging processes and remove only the staging namespace,
   routing, temporary secrets and test data. Recheck production containers.

Offline tests cover malformed hostnames and SOCKS requests, direct and
mixed DNS rebinding records, IPv4 and IPv6 private/metadata addresses, explicit
non-443 ports, and that connect receives only a validated numeric IP. They do
**not** perform real external requests. Generic SearXNG, production egress,
and default GoreeCloud Search configurations are unaffected.

## GitHub-hosted ephemeral network topology qualification

The `search-ephemeral-staging-topology.yml` workflow now runs a
**temporary, non-production** Docker topology on a disposable GitHub-hosted
runner. The integration harness
`tests/goreecloud/ci_ephemeral_staging_topology.py` creates two randomly named
Docker bridge networks, one with `--internal` for the synthetic Search
visitor and gateway, and one external-only bridge for a synthetic provider
fixture and gateway. There are **no published ports, production mounts,
live Search queries, access tokens, Tor relays or user data**.

The synthetic visitor cannot route directly to a fixture provider, a public
Internet target or cloud metadata; all direct probes must fail with an
unreachable/administratively prohibited errno rather than merely refusing a
connection. A minimal deliberately synthetic gateway relays exactly one fixed
marker to a minimal synthetic provider fixture. The provider replies with
the actual connection peer's private bridge address; the test confirms this
is the gateway's egress-bridge address rather than the visitor's internal
address. All fixture processes and Docker bridges are removed automatically
and verified absent at the end of the CI job.

**The synthetic CI gateway is NOT the product's DNS-pinned SOCKS5H gateway.**
This topology proves kernel/Docker isolation only for this ephemeral runner
and visitor path, not that an actual remote GoreeCloud Search installation
cannot bypass its gateway. The synthetic provider observes a **private bridge
IP**, not a public remote server IP. It does not verify a real upstream
provider, a deployment firewall, its DNS rebinding resistance, reverse proxy,
header redaction, user IP masking on the Internet, DNS logs, or production
readiness. Those require a distinct owner-authorized hosted environment and
controlled external observation. This workflow must never be used as
permission to expose Search or mark security issue #21 resolved.

## Acceptance tests (synthetic fixtures only)

| Test | Required evidence |
| --- | --- |
| Provider sees server, not visitor | Controlled HTTPS echo/test provider receives remote server egress IP, no visitor IP; compare from a separate authorized test client. |
| Outbound metadata and headers | Capture the staging outgoing request at the controlled test provider. No client cookie, user IP, tracing ID, referring origin, or browser fingerprint headers. Search query must be synthetic. |
| Missing opt-in | Leave `GOREECLOUD_SERVER_MASKED_EGRESS` unset and prove the application rejects outbound requests before creating a client. |
| Proxy downgrade | Supply a host proxy variable, malicious per-request proxy setting, HTTP target or disabled TLS and prove it cannot redirect staging egress. |
| Image SSRF | Signed URLs using localhost, private IPv4/IPv6, metadata addresses, malformed authorities, and nonstandard ports receive HTTP 400 before any upstream call. |
| Redirect SSRF | Controlled HTTPS image endpoint returns 302 to an internal service; the proxy refuses the redirect and sends no request to the internal destination. |
| DNS rebinding | Controlled public-looking domain resolves to a private target or changes its answer between requests. Observe firewall denial at the network namespace; URL validation alone is insufficient. |
| Active content | Controlled image sources with `image/svg+xml`, HTML, or ambiguous octet-stream must be rejected. Raster-only responses should be served with `nosniff`. |
| Browser referrer/navigation | Search pages use POST/no-store/no-referrer; loading an explicit external result or embedded video may reveal the browser IP and must not be misrepresented as proxied browsing. |
| Logs and retention | Search query, upstream request URLs, visitor address, tokens and headers absent from app, reverse-proxy, sidecar, DNS and error logs under normal/error paths. |
| Provider failures | Rate limiting, CAPTCHA, DNS failure, timeout and gateway outage do not result in direct fallback, unapproved provider selection or query-bearing error logging. |
| Resource and recovery | Containers are resource-limited; storage/SQLite warning addressed; revoke the staging process, routing and state without touching production containers or DNS. |

## Release criteria and rollback

**Do not make Search public**, merge the draft PR, or mark the product Stable until every above test relevant to the intended topology is evidenced with a precise code SHA, staging environment ID, sanitized trace, independent packet observation and proportionate rollout/rollback. Also complete GoreeCloud Identity, limiter, Privacy Shield, Glaze/device/accessibility, dependency/security audit, service-specific firewall and target storage compatibility.

Rollback affects **only** the staging workload: terminate its deployment, remove its staging-only credentials, routing and data per retention policy, and re-confirm existing production container availability. No production database, DNS, Caddy route or VPN configuration may be changed as part of the staging exercise.

**Control:** The user explicitly ruled out Tor. Do not introduce a Tor requirement, Tor binary or Tor circuit into this plan.
