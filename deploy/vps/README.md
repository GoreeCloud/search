# GoreeCloud Search — Private VPS deployment

**State:** Development-only; requires live verification before release. The production hostname `search.goreecloud.com` is reserved for the Stable release and MUST NOT serve this Development deployment.

## Architecture

- Domain: `search-dev.goreecloud.com`, with Caddy DNS-01 TLS and **NetBird-only HTTP access**.
- Docker network: external `proxy`; no published Search or Tor ports.
- Application source: pinned GoreeCloud Search commit. Runtime secret in a protected, untracked env file on the VPS.
- Tor: local SOCKS5H relay with application process in the same network namespace. The Search application must refuse direct provider egress if that proxy is unavailable or misconfigured.
- Approved adapters depend on the exact checked-out Development revision. The older privately deployed `dev-parser-56a4823` image predates the seven-source candidate; inspect the selected source registry and profile before a new build. Source inclusion is not proof of live reachability.

## Disposable network-isolation rehearsal

The `disposable-egress-topology` GitHub Actions job runs
`tests/goreecloud/ci_ephemeral_staging_topology.py` on a fresh CI runner.
It creates **two Docker-internal bridges**, a synthetic visitor, gateway and
provider. It checks that the visitor cannot directly reach the provider,
public IPv4/IPv6 or metadata targets, or resolve an external DNS name. Only
the synthetic gateway can relay a fixed marker to the synthetic provider.
It then disconnects the gateway, requires fail-closed behavior, reconnects it
and verifies synthetic recovery. The script removes its test containers and
networks; it never attaches to the VPS `proxy` network and uses no real terms,
production mounts or public host ports. The laptop's rootless Podman CNI lacks
the compatible `--internal` network plugin, so a failed local attempt is **not**
evidence of isolation; the CI Docker runner is the executable test target.

**Not release acceptance:** These synthetic tests do not run Search's actual
Tor SOCKS5H relay, test current provider anti-bot responses, prove public exit
IP masking, verify Docker host firewall/DNS-rebinding prevention, qualify the
existing VPS (whose `proxy` bridge is not internal), or exercise real Search
image rollback. Tor bootstrap logs and container health are not proof of those
requirements. These checks require separately isolated staging, approved egress
controls and retained rollback evidence before any deployment/promotion.

## Read-only admission audit for the current Search/Tor deployment

Run `python3 utils/goreecloud_search_egress_admission.py` from an authorized
checkout on the Docker host **before** considering any Search image promotion.
This script only inspects the two fixed Search/Tor containers and their Docker
network definitions; it neither makes provider requests nor changes any
containers, networks, Caddy rules or host firewall settings. It emits bounded
finding names without serializing Docker environment variables or IP addresses.
Exit code **2** always means `NOT_QUALIFIED`, even when structural settings
pass: Docker metadata alone cannot prove forced Tor egress or deny-by-default
DNS/metadata/IPv6 firewall enforcement. A shared Search/Tor namespace on the
non-internal `proxy` bridge is explicitly flagged as having a potential direct
route. Treat the report as a release blocker, not a deployment health check.

The offline regression suite is
`python3 -m unittest discover -s tests/goreecloud -p test_egress_admission.py`.
A future staging configuration must separately verify **actual** Search/Tor
isolation, Tor relay availability/failure, direct-connection denial, DNS behavior,
provider-viewed identity, a pinned runnable Search image and a tested rollback.
Do not reconfigure the currently running VPS to make this metadata report green.

**Observed, October 20, 2026 (read-only on the existing VPS):** The audit returned
`shared_namespace_has_external_route`, `search_writable_root`,
`tor_writable_root`, and `host_firewall_and_live_leak_tests_unverified`.
The running `goreecloud/search:dev-parser-56a4823` container was healthy.
These are measured structural findings, **not** an observed query leak or an
active exploitation claim. The staging candidate and its rollback remain separate
from this older deployed Development image.

## Deployment gates

1. Confirm correct GoreeCloud GitHub identity and exact source commit. From a dedicated, reviewed, clean checkout of the approved Development revision, build the custom builder and application images with an explicit commit provenance label:
   ```sh
   test -z "$(git status --porcelain)" || { echo "Refuse to build a dirty checkout" >&2; exit 1; }
   SOURCE_SHA="$(git rev-parse HEAD)"
   # Preferred source-safe staging builder: generates version_frozen.py from this
   # commit, uses a revision-specific builder, verifies both image OCI labels,
   # and neither pushes nor deploys containers.
   bash scripts/build_pinned_staging_image.sh "$SOURCE_SHA"
   ```
   **Manual build alternative (do not run in addition to the preferred builder):**
   The version file is gitignored and must be generated from the *same* pinned
   clean checkout before Docker COPY. The following commands are only for an
   authorized checkout where `SOURCE_SHA` was resolved and verified above:
   ```sh
   python3 searx/version.py freeze
   test -f searx/version_frozen.py
   IMAGE="goreecloud/search:vps-${SOURCE_SHA:0:12}"
   docker build -f container/builder.dockerfile -t localhost/searxng/searxng:builder .
   docker build -f container/dist.dockerfile \
     --build-arg VCS_REVISION="$SOURCE_SHA" \
     --build-arg VCS_URL="https://github.com/GoreeCloud/search" \
     --build-arg VERSION="dev-${SOURCE_SHA:0:12}" \
     -t "$IMAGE" .
   IMAGE_REVISION="$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$IMAGE")"
   test "$IMAGE_REVISION" = "$SOURCE_SHA" || { echo "Image revision does not match the source" >&2; exit 1; }
   printf 'Qualified candidate: %s (source: %s)\n' "$IMAGE" "$SOURCE_SHA"
   ```
   A source-revision label establishes declared provenance, not a reproducible or cryptographically verified image; record and verify the local image ID/digest, build inputs and rollback target separately before staging. This step must not push an image or replace a running container.
2. Set `SEARCH_IMAGE` to the exact verified image tag emitted in step 1 (for example, `goreecloud/search:vps-<12-character-source-commit-prefix>`) and set `SEARCH_SECRET` (32+ unique characters) in a private `0600` env file; never commit or print the secret.
3. Validate Compose and startup health with `docker compose --env-file /protected/path/private.env -f deploy/vps/compose.yaml config` and `up -d`.
4. Verify Tor bootstraps, DNS does not leak, exact Search image is running, health/readiness endpoints respond, query POST privacy limits apply, and providers work under their terms.
5. Back up the existing VPS Caddyfile before appending `Caddyfile.search`; use Caddy validate before reload. Confirm public clients receive 403 and NetBird clients reach Search over TLS.
6. If verification fails, restore the original Caddyfile and reload Caddy, then stop only this Compose project. Preserve existing Caddy sites and unrelated workloads.

This profile is **not a public release**. Before opening to the Internet, complete appropriate rate limiting, abuse prevention, anonymous egress verification, real-provider reachability, privacy/security review, backup/recovery and user acceptance.
