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

**Boundaries of the older-image rehearsal above:** No user searches, public
Search exposure or provider availability probes were performed. Its results
did not qualify direct-provider fallback under every code path, DNS rebinding,
app image provenance, visitor-IP masking, seven-provider reliability,
new candidate-image rollback, public ingress or Stable release. The separate
candidate-image rehearsal below adds limited staging rollback evidence.

## Seven-provider candidate image and rollback rehearsal — October 20, 2026

The earlier old-image rehearsal above was followed by a **separate actual
candidate-image rehearsal**, using only the isolated Docker staging project:

- Pinned source commit: `d828a1c556dfb7ed111525af91a19fb6973a8931`.
  The builder Docker build passed. The first distribution-image attempt
  correctly failed because the gitignored `searx/version_frozen.py` had not
  been generated. Generating it using `python3 searx/version.py freeze`,
  verifying the source short SHA, and rebuilding succeeded.
- Built image: `goreecloud/search:staging-d828a1c556df`, local Docker image
  ID `sha256:6e0104bfa6ea1c65c241f8a75772975ce33bb10b6df65b4d7bc1a61160975d63`.
  OCI revision and source labels matched the pinned GoreeCloud GitHub commit.
  This is **declared provenance**, not independently reproducible or signed
  supply-chain attestation.
- The real staging Search, Tor and relay containers ran with the new image.
  Search had **only** the internal Docker bridge; Tor alone also had outbound
  bridge access; direct public/private/metadata IPv4 and public IPv6 attempts
  from Search returned `ENETUNREACH`; external DNS did not resolve.
- Fixed HTTPS Tor Project attestation through Search's local SOCKS5H relay
  returned HTTP 200 / `IsTor=True`; loopback `/readyz` and `/` returned
  HTTP 200 from the new candidate. The homepage displayed all seven approved
  source names, and the previously missing Ecosia adapter file existed.
  These do **not** prove any upstream search provider returned results.
- **Staging rollback:** replaced only the isolated Search and relay image
  with the preexisting `goreecloud/search:dev-parser-56a4823`, verifying
  actual Docker image ID and `/readyz` HTTP 200. **Restore:** switched staging
  back to `goreecloud/search:staging-d828a1c556df` and verified image ID,
  `/readyz` HTTP 200 and homepage HTTP 200. The real live Search service
  was never restarted, upgraded or replaced.
- **Candidate Tor outage and recovery:** stopped only the isolated staging Tor
  container. A new fixed HTTPS attestation through SOCKS5H failed closed with
  `ProxyError`; restarting that Tor container restored `IsTor=True`.
- **Teardown:** all three isolated staging containers and both disposable
  networks were removed. The unrelated live Search image remained the older
  `dev-parser-56a4823`, healthy, with its Tor container still running.

The missing-version packaging problem was then addressed by
`scripts/build_pinned_staging_image.sh`, integrated into Development commit
`cc256fad7e5a04c22567080cd81b83a6a6d46916`.
A **fresh checkout of its tested PR head**
`26c3cd26626d1911b2b3992779f6a79e3b3c41a5` successfully ran that script
on the VPS, generating pinned version metadata and using a revision-specific
builder. It produced local image `goreecloud/search:staging-26c3cd26626d`,
ID `sha256:411a15829fbeaa3cd167a3d1372fa19bd6fdb0503fe1a9b1fe3ce1d4573020e4`,
with matching OCI source and revision labels. The exact PR head passed all
14 CI checks before Development integration. That second image was **built
and verified but not deployed** to staging or production. No claim of
bitwise reproducibility or a build of the subsequent merge SHA is made.

**Still NOT QUALIFIED for Stable:** real provider results and challenge/429
handling, production firewall and DNS-rebinding/IPv6/metadata guarantees,
Tor SOCKS listener scope on its outbound bridge, protected ingress and rate
limiting, external visitor IP privacy, application data-migration rollback,
image build reproducibility/signatures, and seven-provider acceptance remain
open. Staging-only rollback is not production rollback.

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
while the unrelated live Search/Tor containers are still healthy. The
separate candidate-image test above verified staging image rollback and
restoration; teardown is **not** a test of production cutover or data rollback.
Keep [security issue #21](https://github.com/GoreeCloud/search/issues/21)
and [source/provenance issue #33](https://github.com/GoreeCloud/search/issues/33)
open until the missing real acceptance gates are satisfied.
