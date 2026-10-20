# GoreeCloud Search — free-first live Development cutover verification

**Verified October 20, 2026. Scope: `search-dev.goreecloud.com` only. This is a Development release, not Stable.**

## Source, image, and checks

- Authorized GitHub account: **GoreeCloud**. Candidate source code and Compose at exact commit `195b809575ddd1e5dc68ebcaabf832e8d349931c` in draft PR #65, based on free-first budget PR #64 at `5cdf5e67e3e1c879f73d45e05eb29bf62bf2435a`.
- Local complete GoreeCloud Search unit/contract suite: **301 of 301 passed** (includes six new canary layout/recovery contracts).
- Four exact-head GitHub Actions push and pull-request workflows: **all passed**:
  - Foundation push: https://github.com/GoreeCloud/search/actions/runs/39480500738
  - Foundation PR: https://github.com/GoreeCloud/search/actions/runs/39480555761
  - Native Search push: https://github.com/GoreeCloud/search/actions/runs/39480500578
  - Native Search PR: https://github.com/GoreeCloud/search/actions/runs/39480555678
- VPS local pinned Docker image: `goreecloud/search:staging-195b809575dd`, OCI-declared revision `195b809575ddd1e5dc68ebcaabf832e8d349931c`; Docker image ID `sha256:6b1c9cbbbf8a4cff949525b3eaf94b79b56afcc524e6b114b51d8c09efb7faac`. No registry push and no cryptographic supply-chain attestation claimed.

## Runtime canary

- Separate `goreecloud-search-free-canary` project: Search on its own direct provider-egress bridge plus internal app link, and Caddy ingress on internal app link plus the existing `proxy` bridge, with unique alias `goreecloud-search-free-canary-gateway`. **No host-published Docker ports**, no Tor sidecar, no paid API token or subscribed provider, no reused Search volumes.
- Search container became **healthy** before its ingress started; the original `goreecloud-search` and `goreecloud-search-tor` remained running/healthy and were never replaced.
- A disposable proxy-bridge client received HTTP 200 readiness/homepage and **24 real result cards** for a nonpersonal Web metasearch combining DuckDuckGo, Bing and Startpage. The existing rate budget yielded 429 with `Retry-After` when exceeded. Restarting the candidate Search container returned to healthy without altering the old service.

## Live HTTPS cutover and measured rollback

- Preflight: laptop on authorized NetBird connection reached `https://search-dev.goreecloud.com/` and `/readyz` with HTTP 200 and valid TLS against the **old** Search; the live Caddy configuration validated.
- Generated two restricted-permission (**0600**) Caddyfile copies on the authorized VPS: one byte-identical rollback backup of the old configuration and one candidate differing only in the **single** Search reverse-proxy upstream. Verified that the Search virtual host's NetBird CIDR matcher `100.64.0.0/10`, 403 denial branch, TLS configuration, and every other host were unchanged. Candidate configuration validated using the installed Caddy image and through the existing running Caddy container.
- Reversible in-memory Caddy reload to the new alias: NetBird laptop saw the new free-first homepage, HTTP 200 readiness with TLS certificate verification success, and **28 real free metasearch result cards** over HTTPS.
- Non-NetBird Docker client from the `proxy` bridge was denied by the Search HTTPS virtual host: **HTTP 403 Forbidden**, confirming the access rule remained in effect for that tested path.
- After the successful in-memory test, persisted **only the Search reverse-proxy upstream** to the host's bind-mounted Caddyfile (preserving its inode, owner, original private 0600 permissions and the untouched rollback backup), validated and reloaded. Verified new free-first homepage and HTTP 200 readiness again over authenticated NetBird HTTPS.
- **Actual recovery rehearsal:** reloaded the old backup into the running Caddy process, verified the original Search homepage, HTTP 200 readiness and valid TLS over NetBird, then reloaded the persisted new Caddyfile. Verified new free-first homepage, valid TLS, HTTP 200 readiness and **30 real result cards** through the restored free-first route. Tested non-NetBird path again: still HTTP 403.
- Final readback: free canary Search **running/healthy**, canary ingress **running**, original Search/Tor **running/healthy**, original Caddy **running**, and host Caddyfile configured for free-first. The old complete Caddyfile is retained securely on the VPS as the rollback source; no DNS, NetBird address, TLS policy or other Caddy site route changed.

## Current limits and release work

**Development, not Stable.** Only three no-subscription public-interface Web providers produced verified nonempty results in this path. Brave, Qwant, Google and Ecosia remain unqualified for dependable response; their 403/429/CAPTCHA or parser failures must not be circumvented. Category-by-category result quality, image/news/video reliability and cross-day availability remain to be measured.

The 12-search-per-minute global limiter is a single-worker safeguard only; the Search host is still NetBird-only. Public/multiuser access would require authenticated ingress and distributed per-client abuse controls. The new direct HTTPS model intentionally exposes the VPS IP and submitted search terms to selected providers, as the owner requested. Production-grade monitoring, longer-window uptime, full URL/SSRF defenses, reproducible release provenance, full dataset/backups policy and promotion into the stable/default Git branch have **not** been certified. Historical paid API research PR #62 is superseded; **no paid accounts or API keys** are active.

For recovery, validate the securely retained backup and reload the original `goreecloud-search-gateway:8080` upstream, then verify the old service and TLS from the NetBird laptop. Keep the original containers and volumes until release qualification is complete. Do not claim Stable solely from this functional cutover.
