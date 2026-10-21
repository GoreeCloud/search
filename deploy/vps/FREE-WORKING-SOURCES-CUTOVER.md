# Tested free sources — Development canary and governed cutover

**October 20, 2026 — candidate only, not deployed.**

GoreeCloud Search already serves working free SearXNG metasearch on the owner-only
NetBird Development hostname. The currently live Caddy Search upstream is
`goreecloud-search-free-upgrade-gateway:8080` running pinned source
`64c4cab8e2bdf538d718a8409e51ee76613133c0`; original free canary and
Search/Tor remain protected rollback options. Do not change or delete them
while testing a new source preset.

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

The historical hardcoded `free_upgrade_preflight.py` validates the
**previous** canary-to-upgrade route and is **not** sufficient for this new
upgrade-to-working cutover. A new read-only exact-head gate for these names,
owners, image IDs and backup must be audited before a live route switch.
The current Development service is **not Stable**.
