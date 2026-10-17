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
