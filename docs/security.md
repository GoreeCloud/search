# GoreeCloud Search security and privacy (development alpha)

## Network

- The crawler only accepts HTTPS, exact approved hostnames and standard 443.
- Every crawler request, including robots fetching, must specify its local
  pinned-IP HTTPS CONNECT proxy or is rejected. The proxy refuses non-CONNECT
  requests, arbitrary ports, non-allowlisted hosts and any DNS response
  containing a non-global address. TCP dials the checked IP rather than a
  re-resolved hostname; the client verifies HTTPS certificates end-to-end.
- Cross-host HTTP redirects and client-side meta-refresh are disabled.
  Local files, data URIs and FTP download handlers are disabled explicitly.
- Requests are bounded by time, page size, concurrency, depth and retry count;
  connections are bounded by idle time, concurrency and tunnel byte budget.
- The SQL frontier serializes URL claims by host and applies cooldowns shared
  by concurrent worker instances.

**Important:** This reduces the precheck DNS-rebinding problem but does not
replace an operating-system sandbox. Run in a non-root account/container with
no secrets, no mounted privileged sockets and a restrictive host firewall
blocking direct egress to private, link-local, loopback and metadata addresses.
Proxy controls only traffic that actually uses it. Robots access and
failure-policy behavior need independent real-site tests before expanding
beyond explicitly consented seeds.

## Removal and content governance

A manual operator command stores a durable exclusion and requests a
search-visible OpenSearch delete. Workers must be stopped first to avoid
cross-store races. There is no automated site-owner verified claim process,
appeal system or backup-deletion propagation yet. Crawl and indexing state
must not be represented as an authoritative right to republish third-party
content.

## Query privacy

The read-only API does not create query profiles or persistent raw-query
histories. No external telemetry script is bundled. The development API
uses Cache-Control no-store, Referrer-Policy no-referrer and
X-Content-Type-Options nosniff. Uvicorn should run with --no-access-log.
Browser history, proxy logs and ingress can still retain GET parameters,
and must be independently configured to redact query strings before
public deployment. Search results are escaped React text, not executed HTML.

## Open release gates

Review third-party vulnerabilities and provenance, prior historical GitHub
secret notifications, failure modes for robots fetches, live crawler network
containment, resource quotas, anonymous query abuse, admin authentication,
production OpenSearch security and TLS, deletion reconciliation, privacy
policies, snapshots and tested restores, and accessibility/performance
benchmarks. This document records intended controls and current source, not
production acceptance or certification.
