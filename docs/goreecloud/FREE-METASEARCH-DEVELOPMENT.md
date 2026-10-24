# Free-first GoreeCloud Search — Development candidate

**October 20, 2026.** Owner intent supersedes commercial-API pursuit: simple,
free SearXNG metasearch, with no commercial accounts, no per-search charges, and
no requirement for Tor or other special anonymity tooling.

## Design

The **additive** profile `configs/goreecloud/settings.free-first.yml` keeps
the approved SearXNG public-interface adapters for Brave, Startpage, Qwant,
DuckDuckGo, Ecosia, Bing and Google (where available), including image/video/
news category adapters. It sends ordinary direct HTTPS requests. There is
**no Tor relay, no paid API credential, no commercial-provider fallback, and
no hidden substitutions**. An upstream CAPTCHA, rate limit, 403, 429 or
missing parser still surfaces as a failure rather than being circumvented.

The optional disposable `deploy/vps/compose.free-metasearch-staging.yaml`
has only Search and a fixed-upstream Caddy ingress proxy. Search attaches to a
provider egress bridge plus an isolated app-only bridge; the ingress proxy
attaches to that app bridge and an explicitly named separate **scratch**
ingress bridge. No host ports, live Caddy network, NetBird tunnel changes,
live source mounts, user credentials or reused private Search data.

Free metasearch isn't zero-cost hosting: the VPS, bandwidth, storage and
maintenance still cost money, and upstream engines may impose automated
traffic restrictions. **No additional API subscriptions or search fees.

## Bounded single-user admission

This free-first candidate sets a **global 12-search-requests-per-60-seconds**
single-worker budget. A rejected search returns HTTP 429 with an actionable
`Retry-After` header, without logging or storing user IPs, queries or cookies.
Health/readiness and static browsing do not consume the search budget.
The configured single Granian worker owns this in-memory token window.
It is intentionally an inexpensive **single-instance** safeguard for the
already NetBird-only Development service, **not** per-user limiting or
distributed enforcement. Before supporting public/anonymous/multiworker
traffic, replace it with an audited shared limiter (e.g., Valkey-backed),
verify ingress identity and enforce upstream fair-use budgets. Do not open
host-published ports as a substitute for these safeguards.
**

## Important disclosure

**Providers can see the staging VPS public IP address and selected query
terms**. The ISP/host and upstream providers can log connection metadata,
as with ordinary server-side web requests. This intentionally does not
offer Tor anonymity. The application still uses POST at the local front end,
does not publish ports in the scratch profile, does not enable third-party
autocomplete, and keeps upstream URL/metadata controls; these are baseline
engineering safeguards rather than a paid privacy feature.

## Rehearsal and release requirements

Only stage from a clean exact source SHA and locally verified pinned Search
image. Confirm the scratch bridge is separate from the live proxy network,
create a session-only 32+ character secret and check Docker Compose config.
With an already inspected local Caddy image, start only the scratch project.
Perform local readiness and a **small number of synthetic public test
searches** (no personal terms, no CAPTCHA workarounds), report working
results and failures per source, and check no host ports. If providers
respond 403/429 or CAPTCHAs, cease testing those sources.

Tear down **only** this scratch project and scratch bridge after checks.
Do not deploy over the existing Search/Tor/Caddy pair or call Search Stable
until core source results, authentication, request limiting, runtime
monitoring, update and production rollback are verified.

Commercial-API research PR #62 is historical due diligence, not the selected
product architecture. Its existing Gmail vendor inquiry remains unsent.

## October 20, 2026 — tested free-source preset (new candidate, not deployed)

The free-first VPS Development hostname is already serving the prior validated
upgrade binary `goreecloud/search:staging-64c4cab8e2bd`, with old free canary
and protected Caddyfile backup retained for rollback. The following change is
a **separate follow-up source candidate** and is not yet active on that domain.

For a new browser without a saved provider cookie, the additive free-first
profile now selects **Tested free sources**: DuckDuckGo, Bing and Startpage
(Web); Bing Images; DuckDuckGo and Bing Videos; and DuckDuckGo News. This
reflects verified synthetic searches from the existing Development VPS, not a
promise that the providers will be available on every request. The option is
explicit and visible in Settings; users may still select **All Sources** or
any existing individual provider. No provider is secretly substituted on
failure. Saved All Sources and individual choices override the new default;
legacy `both` cookies still mean All Sources. The separate Tor/private
configuration retains its legacy All Sources default.

The homepage, About, Privacy and Settings disclosures are updated to distinguish
the **currently deployed** direct-HTTPS, non-Tor, no-paid-API service from the
older recovery infrastructure. Providers still see the VPS public IP address
and submitted search terms. The in-process 12-search/minute global budget,
NetBird-only reverse proxy and baseline protections are unchanged.

Release remains subject to exact-head source and CI checks, disposable
synthetic provider/category smoke, and a separate narrowly reversible
Development upgrade. It is not Stable or a public launch.
