# GoreeCloud Search — Development Ingress Security and Public Release Hold

**Scope:** private Search Development source admission; not a live-service or public-release certificate.
**Authority:** GoreeCloud's current operating instructions, current repository configuration, and governed release lifecycle.

## Two distinct hostnames

| Host | Intended visibility | This gate's treatment |
| --- | --- | --- |
| `search-dev.goreecloud.com` | Private, NetBird-only Development | Requires an exact `100.64.0.0/10` client matcher, its sole approved reverse-proxy upstream inside the matching handler, and an explicit 403 for everyone else. |
| `search.goreecloud.com` | Future public GoreeCloud Search | Requires separate public-product security, reliability, provider-rights and release acceptance. This Development check neither provisions nor qualifies it. It refuses a public Caddy block that forwards to the private Development gateway. |

## Offline admission guard

`scripts/search_development_ingress_guard.py` is deliberately read-only. It
inspects an explicitly supplied local Caddyfile, accepts a small audited
directive subset for the private Search site, and rejects ambiguous,
additional, or permissive routing. It does not print the Caddyfile or secret
values, and produces one bounded JSON result.

```bash
python3 scripts/search_development_ingress_guard.py \
  --caddyfile deploy/vps/Caddyfile.search \
  --expected-upstream goreecloud-search-gateway:8080
python3 -m unittest discover -s tests/goreecloud \
  -p 'test_search_release_acl_guard.py' -v
```

`pass_static_only` is limited to the inspected file bytes and specified
upstream. A refusal returns exit status 2 and `blocked_do_not_cutover`. This
guard also backs the `unique_netbird_only_host` check of the established
`scripts/free_upgrade_preflight.py` release review for its legacy and working
gateway phases. The surrounding preflight retains its independent exact-image,
snapshot, owner, network, volume and provider-profile checks.

Adversarial fixtures deliberately reject a bypassing site-level proxy,
public-client fallback proxy, malformed 403, altered NetBird mask, duplicate
handler, unexpected Caddy route/log directives, duplicate host alias,
incomplete braces and a public Search vhost accidentally targeting the private
gateway. An unrelated public site with no Development upstream is not
automatically prohibited; its independent qualification remains outside this
Development-only guard.

## Gates this check cannot satisfy

Before any public service or Dev promotion, retain the separate requirements:

1. Validate the **actual composed** Caddyfile using the exact running Caddy
   binary and resolve any imports, snippets, matchers, DNS and proxy aliases.
2. Verify that an authorized NetBird client succeeds and a truly non-NetBird
   client gets 403, with TLS verified and no direct Search container port.
3. Confirm privacy, multiuser rate limiting, abuse/SSRF defenses, provider
   availability and provider-contract rights for each data source. The
   Google/Bing/Brave native-fusion vision does not itself grant licensed access
   or redistribution, and an offline adapter does not prove live SERP coverage.
4. Prove precise deployed image/source provenance, secret handling, runtime
   isolation, recoverable snapshots, real rollback, representative UI/device
   acceptance, observability and sustained reliability.
5. Complete the governed Seal/Anchor acceptance and separately authorize
   public exposure; do not infer public readiness from CI or a green static
   gate.

**Current finding:** Only repository-source inspection and synthetic offline
tests are covered here. No DNS, NetBird policy, Caddy instance, running
container, public endpoint, provider account or user traffic was changed or
tested by this source milestone.
