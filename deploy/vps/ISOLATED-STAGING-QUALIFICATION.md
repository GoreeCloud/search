# GoreeCloud Search — isolated staging runbook and evidence

**Status: DEVELOPMENT STAGING ONLY — NOT STABLE / NOT PRODUCTION QUALIFIED.**
Use this separate Compose project only with the GoreeCloud Search source checkout.
It must never replace or attach to existing `goreecloud-search`,
`goreecloud-search-tor`, Caddy, NetBird, DNS, real search volumes or host ports.

## Architecture and security invariants

- Project name `goreecloud-search-isolated-staging`; no host ports.
- Search's Docker namespace connects **only** to `search_internal` (internal
  Docker bridge, IPv6 disabled); direct public, metadata and private-IP routes
  must be unreachable. Do not add a second outbound attachment.
- The local relay shares *Search's* namespace, binds **127.0.0.1:9050** only,
  and forwards bytes to a fixed `tor:9050` endpoint on the internal bridge.
  Search's strict `socks5h://127.0.0.1:9050` policy remains intact.
- Only Tor attaches to the separate `tor_egress` Docker bridge. No host ports
  are published. Docker-internal network checks cannot prove host firewall or
  Tor anonymity beyond the specifically tested requests.
- The Search staging starter probes the real Tor attestation API strictly via
  the loopback SOCKS5H relay before launching Granian. A failed or missing Tor
  gateway blocks startup; there is no direct proxy bypass.
- No staging component writes to the live Search application/cache/index, and
  all staging containers have read-only roots, dropped capabilities and bounded
  memory/PIDs. The stage uses a synthetic unique secret, not the live secret.
- The Tor SOCKS5 listener currently binds to all container interfaces
  (including the isolated project's outbound bridge). Although no ports are
  published, this still needs scope-restriction review before promotion.
- Search's Docker embedded DNS may behave differently under other daemon
  versions; DNS-leak denial must be retested against the actual target.

## Observed VPS rehearsal — October 20, 2026

Read-only checks before and during staging confirmed the unrelated running
`goreecloud-search` application stayed healthy on its older Development
image `goreecloud/search:dev-parser-56a4823`.

Using **that older image only** in a separate disposable Compose project:

- Docker Compose `config --quiet` passed.
- Docker network inspection: `search_internal Internal=true IPv6=false`;
  Search attached only to this bridge. The Tor container alone was also
  attached to the outbound bridge.
- Direct TCP connections from Search to public IPv4, metadata and private
  IPv4 returned Linux `ENETUNREACH`; direct public IPv6 likewise returned
  `ENETUNREACH`. External `example.com` name resolution failed. These
  checks prove only the tested destinations and resolver path.
- The real Tor service reached **100% bootstrap**; an explicit, synthetic
  SOCKS5H Tor Project attestation returned HTTP 200 and `IsTor=True`.
- Initial readiness returned 403 because the required private Host setting was
  missing. Corrected with the approved `GOREECLOUD_SEARCH_PRIVATE_HOST` value.
- A subsequent startup initially failed closed because Search's worker started
  before the relay service. Corrected via
  `scripts/staging_start_search.py`, a bounded Tor-attestation startup gate.
  With that gate, Search logged `STAGING_TOR_ATTESTED` and its loopback
  `/readyz` endpoint returned **HTTP 200 / READY**.
- **Gateway outage:** stopped **only** the disposable staging Tor container;
  a fixed synthetic Tor-check through Search's SOCKS5H relay failed with a
  `ProxyError` rather than falling back directly.
- **Recovery:** restarted only staging Tor; the same Tor-check subsequently
  returned `IsTor=True` through the relay.
- The older Search image reported that the Ecosia engine module was missing.
  It must **not** be used to qualify seven-provider functionality.

**Boundaries:** No user searches, public Search exposure or provider
availability probes were performed. The tests do not qualify direct-provider
fallback under every application code path, DNS rebinding, app image
provenance, public visitor-IP masking, seven-provider reliability, current
candidate-image rollback, public ingress or the Stable release.

## Reproduction and teardown

Only on an authorized, isolated staging host with a confirmed rollback route:
verify the GoreeCloud GitHub identity and pinned source head, choose an existing
verified local *staging* Search image, create a unique staging-only 32+ character
secret in the protected execution environment, and validate:

```sh
docker compose -f deploy/vps/compose.isolated-staging.yaml config --quiet
docker compose -f deploy/vps/compose.isolated-staging.yaml up -d --no-build --pull never
```

Compose requires `SEARCH_STAGING_IMAGE` and `SEARCH_STAGING_SECRET` to be
set in the private shell; never print them, reuse a live secret, or save secrets
in git. Inspect only the `goreecloud-search-isolated-staging-*` containers and
their two project networks. Use fixed synthetic checks, not actual user terms.
A real Search image qualification separately requires exact commit/revision
matching, fresh dependency build and reproducibility assessment.

After each rehearsal, explicitly tear down **the staging project only**:

```sh
docker compose -f deploy/vps/compose.isolated-staging.yaml down --remove-orphans
```

Verify that the two staging networks and three disposable containers are gone,
while the unrelated live Search/Tor containers are still healthy. This is a
staging teardown, **not** a tested rollback of a newly built seven-provider
Search image. Keep [security issue #21](https://github.com/GoreeCloud/search/issues/21)
and [source/provenance issue #33](https://github.com/GoreeCloud/search/issues/33)
open until the missing real acceptance gates are satisfied.
