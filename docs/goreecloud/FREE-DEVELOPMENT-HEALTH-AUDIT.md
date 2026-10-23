# GoreeCloud Search — zero-fee Development health audit

**Updated October 23, 2026 — opt-in operational tool, not a new background service.**

GoreeCloud Search's verified *NetBird-only Development* hostname is
`https://search-dev.goreecloud.com`, currently served by source
`40caeb47a1fd8fc15a60f54e5e383d1a9f280598` from the isolated
`goreecloud-search-free-working` project. The prior
`goreecloud-search-free-upgrade` gateway and the 0600 mode owner-matched
`/srv/docker/caddy/Caddyfile.free-working-snapshot` remain separate rollback
assets. **Nothing in this monitoring addition updates, restarts, or replaces
any live service.**

## Read-only health audit, zero search queries

From an authorized laptop **on the owner's NetBird network**:

```bash
python3 scripts/free_development_watch.py \
  --expected-revision 40caeb47a1fd8fc15a60f54e5e383d1a9f280598
```

This performs only three bounded **GETs** to the exact Development HTTPS
hostname:

1. `/readyz` must return HTTP 200 with `READY`.
2. The homepage must return HTTP 200 and identify the expected source build.
3. `/preferences` must show the explicit, usable **Tested free sources**
   selection for a fresh browser, while retaining **All Sources**. Disabled
   fieldsets and inert template controls do not qualify as usable options.

It uses standard certificate verification, explicitly ignores proxy environment
variables, rejects redirects, caps response sizes, and never follows result
links or arbitrary URLs. It reports only stable check identifiers and
success/failure categories as JSON; no user IP, search term, URL contents,
tokens, cookie contents or result titles. It exits **0 on complete pass** and
**2 on any failed check**. A revision mismatch indicates possible deployment
drift; resolve against verified image and current Caddy route before accepting
a new revision. Do not silently update a revision pin to hide an unreviewed
cutover.

## Explicit free-source smoke (not default)

When a controlled fresh live provider test is appropriate:

```bash
python3 scripts/free_development_watch.py \
  --expected-revision 40caeb47a1fd8fc15a60f54e5e383d1a9f280598 \
  --check-sources
```

Only after all three baseline checks pass, this submits **at most one fixed,
nonpersonal, synthetic query** for each of Web, Images, Videos and News,
**sequentially** and **without alternate-engine retries**. It checks the
transparent selected-source lists, at least one validated public HTTP(S) result
link with a nonempty title, and zero reported upstream failures. Malformed,
private-address, credential-bearing and placeholder links invalidate the
source check even when another valid result is present. Every returned
result must credit only explicitly selected providers, and the visible
primary/merged source labels must agree with represented-source counts and
the explicit **not a provider-contact confirmation** metadata. Unknown or
malformed provider-error attribution also fails the audit. These source
checks operate locally on the existing response and add no DNS lookups or
HTTP requests. It prints only per-category aggregate **usable link**/error counts, never raw
provider URLs or titles. HTTP 403/429 **or any reported upstream provider
failure within HTTP 200 JSON** aborts remaining synthetic checks, since later
categories may reuse the affected provider. Do not bypass provider protections,
CAPTCHAs, blocks or rate limits.

Source choices are DuckDuckGo/Bing/Startpage for Web, Bing Images,
DuckDuckGo/Bing Videos and DuckDuckGo News. Their availability can change and
a single successful synthetic test is **not** sustained reliability evidence.
This path necessarily sends synthetic search terms to public free-provider
interfaces, exposes the VPS public IP to them, and consumes up to four of
the single-worker per-minute request budget. It does not use Tor or paid APIs.

## Boundaries and response

- The audit needs an owner-authorized NetBird HTTPS client; it cannot prove
  non-NetBird denial, Docker network confinement or image identity by itself.
  Verify those independently from the VPS using the existing release gate.
- Do not install a crontab, timer, subscription, new connector, or automatic
  source-fetch schedule merely because this one-shot script exists. An
  ongoing check must be deliberately configured with appropriate cadence,
  alert destination and explicit synthetic-egress permission.
- A failed readiness/build/configuration check is a deployment-health or drift
  alarm; inspect and, if needed, follow the separately tested Caddy rollback.
  A single provider/category failure is an upstream-reliability signal, not
  automatically evidence of a route outage. Do not restart the Search process
  just to clear the global in-memory limiter.
- CI exercises the audit using **fully mocked transport**. CI never reaches
  the private hostname or public search providers; only an actual authorized
  NetBird runtime invocation proves the current Development response.

**Release status remains Development, not Stable.** Signed container
provenance, sustained monitoring policy, full provider availability and
broader security/Stable acceptance are separate unresolved obligations.
