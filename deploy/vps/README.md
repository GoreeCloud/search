# GoreeCloud Search — Private VPS deployment

**State:** Development-only; requires live verification before release.

## Architecture

- Domain: `search.goreecloud.com`, with Caddy DNS-01 TLS and **NetBird-only HTTP access**.
- Docker network: external `proxy`; no published Search or Tor ports.
- Application source: pinned GoreeCloud Search commit. Runtime secret in a protected, untracked env file on the VPS.
- Tor: local SOCKS5H relay with application process in the same network namespace. The Search application must refuse direct provider egress if that proxy is unavailable or misconfigured.
- Only approved Brave Search, Startpage, and Qwant upstream adapters are configured. Source inclusion is not proof of reachability.

## Deployment gates

1. Confirm correct GoreeCloud GitHub identity and exact source commit. Build the custom builder and application images:
   ```sh
   docker build -f container/builder.dockerfile -t localhost/searxng/searxng:builder .
   docker build -f container/dist.dockerfile -t goreecloud/search:vps-COMMIT .
   ```
2. Set `SEARCH_IMAGE=goreecloud/search:vps-COMMIT` and `SEARCH_SECRET` (32+ unique characters) in a private `0600` env file; never commit or print it.
3. Validate Compose and startup health with `docker compose --env-file /protected/path/private.env -f deploy/vps/compose.yaml config` and `up -d`.
4. Verify Tor bootstraps, DNS does not leak, exact Search image is running, health/readiness endpoints respond, query POST privacy limits apply, and providers work under their terms.
5. Back up the existing VPS Caddyfile before appending `Caddyfile.search`; use Caddy validate before reload. Confirm public clients receive 403 and NetBird clients reach Search over TLS.
6. If verification fails, restore the original Caddyfile and reload Caddy, then stop only this Compose project. Preserve existing Caddy sites and unrelated workloads.

This profile is **not a public release**. Before opening to the Internet, complete appropriate rate limiting, abuse prevention, anonymous egress verification, real-provider reachability, privacy/security review, backup/recovery and user acceptance.
