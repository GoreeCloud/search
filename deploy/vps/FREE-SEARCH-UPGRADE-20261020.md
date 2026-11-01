# Free-first Search — independent Development upgrade candidate

**October 20, 2026. Status: upgraded free Search deployed on Development; not a Stable release.**

## Why a second independent deployment

Before the verified October 20 upgrade, the live `search-dev.goreecloud.com` Caddy host pointed at `goreecloud-search-free-canary-gateway:8080`, with NetBird-only remote-IP access and the original private Search/Tor stack retained as a recovery path. Its running free image is `goreecloud/search:staging-195b809575dd`. New development changes include the safe, offline category diagnostic and the SearXNG DuckDuckGo media fail-closed token patch at `7031c1ba8f7cc998ec36c8c3a9c3e0a0350a128c`; this patch **does not** make an upstream HTTP 403 disappear.

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
missing parallel candidate, stale/absent rollback backup, snapshot owner mismatch,
unexpectedly changed live upstream or access matcher, divergent running Docker
image ID versus the inspected pinned image, tag/revision mismatch, a host port
exposed through either Docker binding view, gateway collision, a missing or
writable free-settings bind mount, a settings profile that differs from the
exact Git revision, a disabled 12-searches/minute budget, nonprivate server
settings, or unavailable Docker inspection returns a **blocked** status and
nonzero exit code. Even a passing report is **admission for manual
cutover review only**, not a permit to skip full HTTPS, provider, non-NetBird,
restart, or actual rollback checks.

An earlier route reload attempt on October 20 was blocked before execution, and
its proposed backup/candidate files were cleaned up. At that earlier checkpoint, the active host still used the old free-search
canary and the upgrade had not been deployed. That historical warning is
superseded by the later verified cutover below. **Do not work around any
future blocked route-changing operation.** The preflight is designed for
pre-cutover admission and should not be expected to pass once the live route
points at the new gateway.

This is a Development deployment process. Adding a second canary, a passing
preflight, or a green CI workflow alone does not make the new version live or Stable.


## Verified live Development upgrade and actual rollback — October 20, 2026

The owner expressly authorized the controlled cutover. Authorized GoreeCloud
GitHub login, exact source revision, running old/new Docker identities, immutable
local image ID, free settings mounted read-only, network split, nonpublic ingress,
health and 0600 backup were checked by the unchanged release checker at
`6b5e4be87882062a042f0392c136fbd74e024bc7`: **25/25 passed** with
`admitted_for_manual_cutover_review` before any traffic change.

- **Upgraded source:** `64c4cab8e2bdf538d718a8409e51ee76613133c0`.
  The running candidate was `goreecloud/search:staging-64c4cab8e2bd`
  with verified image ID
  `sha256:0cf78362ff5fdd1353d32f236e9ba6f29f08b768d2a52e41590796bfe299883a`.
- **Old free canary:** `goreecloud/search:staging-195b809575dd` remained
  running/healthy alongside the candidate. The original Search/Tor remained
  untouched. Neither container published a new public host port.
- **Restricted route change:** The Caddy candidate changed only the one
  `search-dev.goreecloud.com` reverse-proxy target, from
  `goreecloud-search-free-canary-gateway:8080` to
  `goreecloud-search-free-upgrade-gateway:8080`. The old Caddyfile had a
  byte-identical rollback snapshot with the same ownership and 0600 mode.
  Candidate Caddy validation passed and an **in-memory reload** succeeded.
- **NetBird and response verification:** Laptop HTTPS readiness/homepage
  returned 200 with verified TLS. A separate non-NetBird client received
  403 over TLS. Bounded real synthetic searches using the live hostname
  returned **17 Web, 94 Videos and 29 News** valid links with zero provider
  errors in those categories.
- **Rollback really executed:** Reloading the old bind-mounted Caddyfile
  restored build `searxng/2026.10.20+195b809575` on the verified HTTPS
  homepage (readyz=200). Reloading the validated upgrade candidate restored
  `searxng/2026.10.20+64c4cab8e2` (readyz=200). Both directions were
  verified from the NetBird-connected laptop, not merely inferred from backups.
- **Persisted route verified:** Wrote exactly the validated one-upstream change
  to the existing bind-mounted Caddyfile *in place* (preserving the bind-mount
  inode), synced, validated the mounted version and reloaded Caddy from that
  persisted path. Fresh live homepage/readiness remained 200 with valid TLS
  and upgrade generator `+64c4cab8e2`; external/non-NetBird request
  remained **403**. The actual Caddyfile was confirmed to differ from the
  retained original snapshot by the one Search upstream only. Both are
  mode 0600 under the same owner. Temporary copies containing DNS credentials
  were cleaned after verification.

**Final observed state:** The upgraded *free SearXNG* service is live on the
NetBird-only Development hostname. Its original free canary and retained
protected old Caddyfile snapshot remain available for rollback. No new paid
API subscription/account, DNS, NetBird rule, other vhost or Tor requirement was
introduced. The deployment is **Development, not Stable**.

**Unresolved:** A single DuckDuckGo Images synthetic query returned
zero result links and one reported `parsing error`; Bing Images still
produced usable results in the combined test. This alone does not establish
whether the upstream token lookup, parser or provider restriction is the root
cause. Do not evade provider access controls. Remaining Stable requirements
include long-running reliability, source/category failure recovery,
release/provenance and complete security acceptance. The rollback snapshot
must be retained until the governed rollback retention policy permits its
removal.
