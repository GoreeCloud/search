# Security and privacy boundaries — development alpha

## Crawling

- Only explicitly seeded, valid public HTTP(S) hosts may be requested.
  Discovered links remain within those exact hosts; no global crawler expansion.
- Direct IP literals, credentials in URLs, localhost-like names, unusual ports,
  non-global DNS addresses and cross-host redirects are rejected.
- Scrapy respects robots.txt and uses bounded delay, concurrency, depth, page
  size, timeouts and retries. HTML meta robots and X-Robots-Tag noindex are
  excluded from indexing. No cookies or Telnet console are enabled.
- WARNING: DNS is validated before the underlying connection and is not pinned.
  A malicious DNS response can change between validation and connection.
  A production crawler MUST have deny-by-default network egress policy blocking
  loopback, link-local, RFC1918, CGNAT, IPv6 ULA, multicast and metadata ranges,
  or use a pinned resolver and transport. Do not run on privileged hosts or
  unrestricted internal networks. Use a constrained sandbox with no sensitive
  credentials and no mounted internal service sockets.
- Historical repo sources have a GitHub secret-scanning notification. The new
  source does not import those files. Investigate/rotate separately.

## Search privacy

- The API does not assign query identifiers, persist queries, or contain
  analytics SDKs. Disable access logs: uvicorn --no-access-log.
- Upstream proxies, ingress, infrastructure metrics, browser history and
  host logs may still capture query strings unless explicitly configured not to.
  Strip query parameters from reverse proxy logs before any public rollout.
- HTTP endpoints and OpenSearch with security plugin disabled are local-only
  developer conveniences, not production configuration.
- Search result descriptions are rendered as escaped React text. The client
  never fetches or executes result HTML and uses external rel=noopener noreferrer.
- API admin operations, authenticated seed submission, owner-verified removals,
  GDPR retention policies and abuse protections remain unimplemented.

## Release blockers

- Threat-model and test DNS rebinding / redirects / IP ranges and egress policy.
- Rotate/revoke any verified exposed historical API credential.
- Add deployed HTTPS, authentication for admin endpoints and secret management.
- Implement operator-verified removal and data delete/reindex propagation.
- Run runtime, restore, dependency, network, load and accessibility acceptance.
