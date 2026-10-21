# Tested free sources — Development canary and governed cutover

**October 20, 2026 — verified live NetBird Development cutover; not Stable.**

Before this cutover, the NetBird-only Development hostname served the
`goreecloud-search-free-upgrade-gateway:8080` upstream pinned to
`64c4cab8e2bdf538d718a8409e51ee76613133c0`. The current active
upstream is now `goreecloud-search-free-working-gateway:8080` (verified
below). The previous upgrade, earlier free canary, and original Search/Tor
remain rollback options; no unrelated services were modified.

## Distinct candidate

`compose.free-metasearch-working.yaml` uses the dedicated
`goreecloud-search-free-working` Compose project and unique
`goreecloud-search-free-working-gateway` proxy alias. Its Search worker has
direct free-provider HTTPS on a distinct egress bridge and a private app-link
network to the fixed-upstream ingress Caddy. Only ingress joins Docker `proxy`.
No host ports, live Search data, Tor dependency, commercial APIs or paid account.

The new default for **fresh browser profiles** is a static, explicitly visible
**Tested free sources** choice: DuckDuckGo/Bing/Startpage Web; Bing Images;
DuckDuckGo/Bing Videos; DuckDuckGo News. Saved choices remain authoritative,
and selecting All Sources again enables all seven approved families. This
is not a guarantee that every upstream provider will respond.

## Deployment gate — do not skip

1. Verify GoreeCloud GitHub identity, exact source-head CI, tested source/image
   identity and Docker image ID, settings/profile hash, one worker and global
   12-search/minute limiter. Require a clean exact-head checkout.
2. Bring up *only* the candidate using its own Compose project with a newly
   generated temporary secret. Never reuse either currently routed gateway
   alias. Check readiness, four categories and selected engines with bounded
   synthetic nonpersonal queries. Do not retry or circumvent 403/429/CAPTCHAs.
   Check no host-published ports and that the Search worker is not on `proxy`.
3. Confirm the current live hostname still uses
   `goreecloud-search-free-upgrade-gateway:8080`, and that both current free
   Search and the new candidate are healthy. Create a protected 0600,
   byte-identical new rollback snapshot of the currently active Caddyfile;
   preserve the older protected rollback snapshot separately.
4. Review exactly one proposed reverse-proxy upstream change for only
   `search-dev.goreecloud.com`, from `goreecloud-search-free-upgrade-gateway`
   to `goreecloud-search-free-working-gateway`. Validate the candidate with
   the running front Caddy binary. Preserve all NetBird 100.64.0.0/10
   restrictions, TLS settings, 403 rules, DNS and other virtual hosts.
5. Use **in-memory** Caddy reload for initial evaluation. Confirm via real
   NetBird laptop HTTPS (valid TLS, readyz, homepage, exact generator revision
   and a bounded synthetic search) and non-NetBird TLS denial (403).
   Rehearse old->new and new->old route reversals, verifying actual generator
   IDs, before persisting the one upstream change.
6. If all gates pass and governed cutover is authorized, persist only that
   reviewed change to the existing bind-mounted Caddyfile without replacing
   the inode. Validate/reload that persisted path; repeat real HTTPS,
   category, 403 and old-instance health checks. Retain protected rollback
   snapshots while the release remains reversible.
7. If any material gate fails, do **not** switch live traffic. Keep the older
   healthy routed Search unchanged, tear down only the candidate project
   and its project networks if safe, and record the exact blocker.

The read-only `scripts/free_upgrade_preflight.py --phase working` checks the
**upgrade-to-working** route, pinned image and running Docker metadata; its
default `--phase legacy` retains the previous canary-to-upgrade behavior.
For the new gate use a fresh protected byte-identical Caddyfile snapshot at
`/srv/docker/caddy/Caddyfile.free-working-snapshot` with matching owner/mode.
The new phase must pass all checks on the exact source SHA before any
manual route change; do not reuse the prior cutover's 0600 snapshot.
The current Development service is **not Stable**.

## Verified live upgrade, exact-head and rollback — October 20, 2026

**Running source revision:** `40caeb47a1fd8fc15a60f54e5e383d1a9f280598`.
The new active Search image is
`goreecloud/search:staging-40caeb47a1fd`, with actual Docker image ID
`sha256:db950fdd2f02003069d1f9b564544c312cc6e64d8cb634fa113142c7ab7d848c`.
This ID and OCI revision label were inspected locally; no cryptographic
signature or registry publish was claimed.

**Source/release checks:** The source passed **364/364** installed-dependency
local Search tests, including six negative working-route release-gate tests,
and bytecode/diff checks. All four exact-head GitHub Actions workflows
succeeded: Foundation push `39533474083`, Foundation PR `39533482523`,
Native Search push `39533474043`, Native Search PR `39533482540`.

**Parallel candidate:** The separate working canary launched with its own
project, dedicated `proxy` alias and read-only, nonroot containers. The Search
worker was healthy, off the shared front-proxy bridge, and had no host ports.
A bounded synthetic probe against only the new gateway returned **29 Web,
35 Images, 78 Videos and 29 News** links with **zero reported source errors**,
and verified precisely the tested-source preset without a browser cookie.
After restarting only the candidate Search worker, 12 synthetic empty-form
requests were accepted and the 13th returned **429 Retry-After: 60**.

**Read-only release admission:** The exact `--phase working` gate initially
returned `blocked_do_not_cutover`, 23/25, solely because a new protected
rollback snapshot did not yet exist. A *new*, same-owner, mode 0600,
byte-identical snapshot was created at
`/srv/docker/caddy/Caddyfile.free-working-snapshot`. The unchanged
read-only checker then returned **25/25**,
`admitted_for_manual_cutover_review`, with the exact active Docker/image and
mounted free profile checks passing.

**Actually verified Caddy switch:** Created a 0600 candidate differing from
the existing front Caddyfile by **one** Search upstream only, old
`goreecloud-search-free-upgrade-gateway:8080` -> new
`goreecloud-search-free-working-gateway:8080`. Validated with the running
front Caddy binary, then reloaded **in memory** without touching the saved
Caddyfile. The NetBird-connected laptop received HTTP 200 readiness and
homepage with valid TLS and generator `searxng/2026.10.20+40caeb47a1f`;
a synthetic free Web query returned **30 actual links**, selected sources
DuckDuckGo+Bing+Startpage, zero errors. A non-NetBird Docker-network client
received **HTTP 403 over TLS** from the same Caddy hostname.

**Rollback actually rehearsed:** Reloading the **old** bind-mounted Caddyfile
restored actual generator `searxng/2026.10.20+64c4cab8e2` and HTTP 200
readiness on NetBird HTTPS. Reloading the **new** candidate restored
`searxng/2026.10.20+40caeb47a1f` and HTTP 200. These are observed
two-way cutovers, not merely backup-existence assertions.

**Persisted and reverified:** Wrote only the validated upstream change into
the *same* bind-mounted Caddyfile inode (preserving 0600 mode/owner), fsynced,
validated the mounted Caddyfile and reloaded from `/etc/caddy/Caddyfile`.
NetBird HTTPS readiness/homepage remained 200 with the working generator;
a new synthetic Web query returned **27 links and zero provider errors**,
automatically selecting the three tested Web engines. The non-NetBird request
again returned 403. Fresh readback confirmed the exact one-upstream diff
against the protected pre-cutover snapshot and both old/current working
Search containers running/healthy. The temporary credential-containing
Caddy candidates were destroyed from the host and Caddy container; only
the protected 0600 release snapshot was kept. The separate scratch project
and its networks were removed.

**Current behavior:** New browser profiles use **Tested free sources**;
existing browsers with a saved All Sources or single-engine cookie retain
that selection. The user can explicitly choose either option in Settings.
No provider is secretly substituted. No paid APIs, Tor requirement,
public host port, DNS or NetBird ACL changes were introduced.

**Remaining release limits:** The deployed Search remains a NetBird-only
Development service, **not Stable**. The limiter is in-process for one worker,
not distributed; free provider availability can change, DuckDuckGo Images
has intermittent parsing/access-denied behavior when explicitly selected,
some of the seven available individual engines remain unqualified, and
long-duration source monitoring, security/provenance and Stable acceptance
are still open. Retain the old healthy `free-upgrade` containers and
protected rollback snapshot until the reviewed rollback-retention gate.
