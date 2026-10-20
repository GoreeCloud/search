# GoreeCloud Search — Private VPS deployment

**State:** Development-only; requires live verification before release. The production hostname `search.goreecloud.com` is reserved for the Stable release and MUST NOT serve this Development deployment.

## Architecture

- Domain: `search-dev.goreecloud.com`, with Caddy DNS-01 TLS and **NetBird-only HTTP access**.
- Docker network: external `proxy`; no published Search or Tor ports.
- Application source: pinned GoreeCloud Search commit. Runtime secret in a protected, untracked env file on the VPS.
- Tor: local SOCKS5H relay with application process in the same network namespace. The Search application must refuse direct provider egress if that proxy is unavailable or misconfigured.
- Approved adapters depend on the exact checked-out Development revision. The older privately deployed `dev-parser-56a4823` image predates the seven-source candidate; inspect the selected source registry and profile before a new build. Source inclusion is not proof of live reachability.

## Deployment gates

1. Confirm correct GoreeCloud GitHub identity and exact source commit. From a dedicated, reviewed, clean checkout of the approved Development revision, build the custom builder and application images with an explicit commit provenance label:
   ```sh
   test -z "$(git status --porcelain)" || { echo "Refuse to build a dirty checkout" >&2; exit 1; }
   SOURCE_SHA="$(git rev-parse HEAD)"
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
