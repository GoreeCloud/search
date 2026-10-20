# Free-first Search — independent Development upgrade candidate

**October 20, 2026. Status: implementation candidate, not a cutover or Stable release.**

## Why a second independent deployment

The live `search-dev.goreecloud.com` Caddy host currently points at `goreecloud-search-free-canary-gateway:8080`, with NetBird-only remote-IP access and the original private Search/Tor stack retained as a recovery path. Its running free image is `goreecloud/search:staging-195b809575dd`. New development changes include the safe, offline category diagnostic and the SearXNG DuckDuckGo media fail-closed token patch at `7031c1ba8f7cc998ec36c8c3a9c3e0a0350a128c`; this patch **does not** make an upstream HTTP 403 disappear.

Never deploy a second ingress service advertising the **same** `goreecloud-search-free-canary-gateway` alias on the shared Docker `proxy` bridge: simultaneous alias registrations could route user traffic unpredictably. Never modify Caddy, NetBird, DNS, or original Search/Tor merely to test a new image.

`deploy/vps/compose.free-metasearch-upgrade.yaml` therefore uses separate project `goreecloud-search-free-upgrade` and fixed new alias `goreecloud-search-free-upgrade-gateway`. It retains the existing isolated Search/provider egress setup, one-worker in-memory 12-search/minute budget, nonroot/read-only containers, dedicated fixed-upstream Caddy ingress, health-gated startup, no host ports, no persistent or production data mounts, no paid APIs, and no Tor requirement.

## Verification gates

1. Confirm authorized GitHub account, clean SHA, image pin, manifest SHA and Docker network alias uniqueness. Inspect host and ingress permissions and never print or commit the session secret.
2. Build a locally pinned Search image from **the same approved release source head**, no registry push or external subscription. Validate Compose offline and all exact-head CI before release.
3. In a *separate* canary project, use a fresh session-only secret and validate readiness, homepage, selected **free** General/Images/Videos/News actual result links, no host-published ports, no paid sources, HTTP 429 on the 13th rapid synthetic request, restart recovery, and fixed net topology. Respect provider rate restrictions: one bounded synthetic check per category, no CAPTCHA or rate-limit bypass.
4. Retain the old and new canaries alongside each other and verify the front Caddy host still uses the **old** gateway before considering a route change. A route switch requires the same single-upstream-only Caddy diff, locked 0600 backup, config validation, in-memory trial, NetBird HTTPS smoke, 403 denial from a non-NetBird probe, persistence and **actual rollback-to-old-and-back rehearsal** proven in the previous canary release. Keep old canary and original Search/Tor available.
5. If any step fails, do **not** modify the active Caddy route. Tear down only the new project and preserve the old Search gateway. Report source/provider issues without guessing their cause. Stable release requires sustained multi-day source reliability, privacy/network/SSRF review, provenance, maintenance and rollback evidence, and explicit stable-branch release acceptance.

## Read-only release admission check

The new `scripts/free_upgrade_preflight.py` is a **gate, not a cutover utility**.
It reads the current private host Caddyfile, an independently created exact
backup, container and image inspection metadata, and prints only sanitized
booleans. It never runs `docker compose`, sends provider queries, exposes
secrets, modifies Caddy, reconfigures NetBird, or follows arbitrary endpoints.

Example from the **authorized VPS** after independently starting the parallel
upgrade and creating a protected exact Caddy snapshot:

```sh
python3 scripts/free_upgrade_preflight.py \
  --image goreecloud/search:staging-64c4cab8e2bd \
  --revision 64c4cab8e2bdf538d718a8409e51ee76613133c0 \
  --snapshot /srv/docker/caddy/Caddyfile.free-upgrade-snapshot
```

The exit code is **0 only if every defined prerequisite passes**. Any mismatch,
missing parallel candidate, stale/absent rollback backup, unexpectedly changed
live upstream or access matcher, unknown image revision, exposed host port,
gateway collision, or unavailable Docker inspection returns a **blocked**
status and nonzero exit code. Even a passing report is **admission for manual
cutover review only**, not a permit to skip full HTTPS, provider, non-NetBird,
restart, or actual rollback checks.

A prior route reload attempt on October 20 was blocked before execution, and
its proposed backup/candidate files were cleaned up. The currently active host
still uses `goreecloud-search-free-canary-gateway:8080` and the old free-search
image; the new image `staging-64c4cab8e2bd` remains a tested, locally cached
artifact, not a live deployment. **Do not work around a blocked route-changing
operation.** The checker should truthfully report `blocked_do_not_cutover`
until a separately reviewed candidate, current protected snapshot, and all
other gates exist.

This is a Development deployment process. Adding a second canary, a passing
preflight, or a green CI workflow alone does not make the new version live or Stable.
