# GoreeCloud Search — isolated private ingress migration candidate

**Status: DEVELOPMENT / NOT RELEASED.** This is an additive, disposable
migration candidate, **not** a replacement for the running VPS Compose stack.
No live Caddy, proxy bridge, NetBird, DNS, service volume, Search container or
Tor container may be modified during these tests.

## Why the existing Compose cannot qualify for Stable

The deployed `deploy/vps/compose.yaml` intentionally shares Search's
namespace with Tor using `network_mode: service:tor`. Tor is attached to the
external `proxy` bridge, so the Search namespace inherits an IPv4 default
route. Read-only inspection of the actual running private Development
deployment found precisely this state. A configured SOCKS5H proxy cannot
prove that every future component will respect it. No actual user-query leak
was established, but this arrangement must not be promoted as a verified
fail-closed private architecture.

## Candidate architecture

`compose.hardened-private-candidate.yaml` has four containers:

- **Search:** only on internal `172.29.247.0/28` Docker bridge, fixed
  `172.29.247.3`, IPv6 disabled and no host-published ports; Granian binds
  `0.0.0.0:8080` **inside the internal-only namespace** to accept the
  private ingress proxy. The startup script rejects unexpected local routing
  before Tor attestation and any search worker starts.
- **Tor:** fixed internal IP `172.29.247.2`, plus a separate outbound bridge;
  listens only on the internal address and accepts SOCKS traffic only from
  Search IP `172.29.247.3`.
- **SOCKS relay:** shares only Search's namespace, accepting loopback
  `127.0.0.1:9050` and connecting to the fixed internal Tor SOCKS port.
- **Ingress:** a separate, image-pinned Caddy container attaches to the
  isolated internal bridge and an **explicitly selected** proxy-style bridge.
  It reverse proxies only to `search:8080`, with no host ports, HTTP request
  logging, open forward-proxy service, or real visitor-IP forwarding into
  Search. Upstream abuse controls and identity enforcement are **still
  required** at the real TLS/VPN front door.

No application content, live caches, live credentials or actual users are
used in this disposable candidate. `goreecloud-search-hardened-gateway` is a
distinct alias, not the existing `goreecloud-search-gateway` upstream.

## Safe synthetic rehearsal

Before starting, verify that `172.29.247.0/28` has no overlap with actual
Docker, VPN or host routing. Only if a separate scratch network is permitted,
create a new Docker bridge such as
`goreecloud-search-hardened-ingress-test-20261020` without host ports.

Use the exact locally built/pinned Search image and an already-inspected local
Caddy image. Supply four session-local environment variables:
`SEARCH_STAGING_IMAGE`, `SEARCH_STAGING_SECRET` (independently generated,
32+ characters, never printed), `SEARCH_CANDIDATE_INGRESS_IMAGE`, and
`SEARCH_CANDIDATE_INGRESS_NETWORK` (scratch bridge, **never `proxy`**).
Then validate Compose config and start only the candidate file:

```sh
docker compose -f deploy/vps/compose.hardened-private-candidate.yaml config --quiet
docker compose -f deploy/vps/compose.hardened-private-candidate.yaml up -d --no-build --pull never
```

Verify the exact pinned app revision, Search-only internal network, outbound
Tor isolation, ingress/proxy network split, absent published ports, successful
fixed Tor Project attestation, private Host acceptance, request headers,
HTTP readiness/homepage, DNS and direct-IP egress denials, Tor outage
fail-closed behavior, and legacy cache bypass. A scratch client joined
**only** to the scratch ingress bridge may request the service with the
approved Development Host header. No external provider searches are permitted.

**Teardown:** use `docker compose ... down --remove-orphans` for this **one**
candidate project, then remove only the named scratch ingress bridge. Confirm
the original `goreecloud-search`, `goreecloud-search-tor`, Caddy, NetBird
and unrelated Docker networks remained unchanged.

## Outstanding release gates

This candidate is not a ready-made production cutover. Before any live
migration, separately review and validate a reversible Caddy route change
from the old `goreecloud-search-gateway` alias to the new ingress, a
non-colliding project/network migration, proper NetBird/TLS authentication,
limiter policy, privacy/retention disclosure, source image supply-chain
provenance, persistent data and configuration rollback, DNS/metadata/IPv6
egress enforcement under the actual host, and responsible Tor exit treatment.

Most importantly, the seven approved external Web providers previously
returned zero usable results through isolated Tor staging. Live provider
rights, sustainable APIs, billing, retention, and repeatable result success
remain **unqualified**. No provider may be relabeled, silently replaced,
rate-limit circumvented, or granted new account credentials through this
network migration. A green homepage or CI result does not make Search Stable.
