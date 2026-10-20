# Free-first Search canary and cutover gate

**Development, October 20, 2026. No automatic traffic change.** User chose free metasearch, direct HTTPS, no special Tor anonymity and no commercial API. The currently deployed `goreecloud-search` and `goreecloud-search-tor` remain the recovery baseline.

## Candidate

`compose.free-metasearch-canary.yaml` uses a **separate project**
`goreecloud-search-free-canary`. Two isolated, nonroot, read-only containers:

1. Search: direct provider HTTPS over its own egress bridge, plus a private app link; a single Granian worker with a 12-requests-per-minute in-memory global search budget; no paid or Tor adapters; a local readyz health probe.
2. Ingress: dedicated pinned Caddy instance attached to the app link and the existing `proxy` bridge using the **distinct** alias `goreecloud-search-free-canary-gateway`. It can forward only to Search, does not expose host ports, and starts after Search health succeeds. It uses the existing reviewed fixed-upstream Caddyfile.

The canary Compose startup by itself does not edit live Caddy. **Verified as of October 20, 2026, however, the separately authorized live Development host cutover has been performed.** The Search host continues to allow only NetBird `100.64.0.0/10`, but its persisted upstream is now `goreecloud-search-free-canary-gateway:8080`. The original `goreecloud-search-gateway:8080` remains an explicitly tested recovery path, with the exact prior Caddyfile securely backed up on the VPS. The existing `proxy` bridge is shared with other GoreeCloud private services, so it must not be treated as tenant isolation. See `FREE-CANARY-LIVE-VERIFICATION-20261020.md` for checks and limits.

## Gated preflight

- Verify GitHub account GoreeCloud and exact source head, PR checks, image ID and OCI revision. The pinned image is not a signed supply-chain attestation.
- Verify `proxy` exists, no canary project or gateway alias collision, no staging leftovers, current Search/Tor/Caddy health, NetBird private DNS/TLS reachability, free host memory, and Caddyfile backup/readback without exposing DNS provider credentials.
- Keep original Search/Tor Compose, data volumes and Caddy route untouched; use a distinct session-only random secret and `SEARCH_FREE_IMAGE`/`SEARCH_FREE_INGRESS_IMAGE` pinned from local inspected images. Configure, then start only the candidate Compose project with `--no-build --pull never`.
- Validate healthy worker; no host ports; runtime free-first settings and 12-request limit; HTTP 200 homepage and readyz through the **new** ingress alias; one or two synthetic, public, nonpersonal searches returning substantive result links from the free DuckDuckGo/Bing/Startpage adapters. Do not hammer providers or evade denial responses.
- Test 12 budget successes, thirteenth 429 plus Retry-After, unaffected homepage, and survival of independent Search worker restart/recovery without touching original live containers.
- Before any actual owner traffic redirect, independently validate authorization, NetBird-only TLS policy, route change and backup integrity, privacy disclosure, monitoring, production server egress/metadata and URL redirect boundaries. Access control must not be widened.

## Traffic switch and recovery are **not automatic**

Only after all gates pass should a reviewed, narrowly scoped replacement of the *one*
`search-dev.goreecloud.com` `reverse_proxy` upstream be attempted, preserving the original NetBird matcher, TLS settings, and every other virtual host. Validate Caddy configuration **before** applying. Keep the old Search and Tor running, then from the NetBird-connected laptop verify TLS, 200-readyz, real free search results, and rate-limiting. Monitor failures and only then retain the change.

For rollback, restore the exact Caddy route backup (including its original upstream `goreecloud-search-gateway:8080`) without changing any DNS secrets, validate before reload, and verify old Search/Tor healthy plus NetBird HTTPS search. A rollback is not qualified by a backup file alone; perform a staging rehearsal of both change directions first.

**Do not call GoreeCloud Search Stable** merely from the now-verified Development canary, live NetBird HTTPS switch and tested recovery route. Those steps passed on October 20, 2026 as recorded in the linked verification report. Stable still requires representative category coverage and sustained free-provider availability, longer-term monitoring, release provenance, complete security/recovery acceptance, and a governed stable-branch promotion. No commercial subscriptions, paid API credentials, or Tor anonymity requirements should be introduced.
