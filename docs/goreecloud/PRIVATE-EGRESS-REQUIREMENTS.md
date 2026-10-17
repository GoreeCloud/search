# GoreeCloud Search — privacy-preserving egress without Tor

**Lifecycle: Development / Draft PR #18. Updated October 17, 2026.**
This is a technical contract and threat model, **not a promise of anonymity or
authorization to expose Search publicly**.

## Privacy promise and limits

The user requests **no Tor requirement**. A remote GoreeCloud Search server
can mask its visitors' source IP from Brave Search, Startpage and Qwant: the
providers receive the hosting server's public egress IP, not the browser's
original IP, provided the reverse proxy and upstream requests do not forward
identifying metadata. An independently trusted non-Tor VPN/SOCKS gateway can
further mask the **server's** IP. Neither arrangement hides the plaintext
search terms from each selected provider. A user browsing from the same host
as the Search server is **not** IP-masked by a direct server request.

The GoreeCloud host, its reverse proxy, upstream hoster, VPN/gateway operator
(if used), and search providers remain distinct trust boundaries. A
single-tenant dedicated server IP or distinctive query text may allow search
providers to correlate requests. Query obfuscation that changes search meaning
is not a reliable privacy guarantee. A user who clicks a result may expose
their browser IP, cookies and fingerprint directly to the destination site;
the server-side search proxy cannot prevent that without separate browser
protections.

## Supported egress modes

GoreeCloud Search always applies HTTPS-only requests, normal TLS certificate
verification, cookie suppression, removal of known client-identifying headers,
URL-free network diagnostics, POST-only query submission and no-store search
responses. All registered provider and image-proxy networks share the policy,
regardless of engine-specific network overrides or privacy UI settings.

### 1. Trusted gateway (default; local developer profile)

`goreecloud.egress_mode: gateway` requires exactly one loopback-bound
`socks5h://` gateway configured for **all protocols**. SOCKS5H delegates DNS
resolution to the gateway. Tor is **not** required; an owner-controlled VPN
gateway or another audited relay is acceptable. When the gateway is missing,
unconfigured or invalid, search fails closed without switching to server-direct
egress. Configuring a SOCKS5H port is **not proof** of the gateway's exit
identity, trustworthiness or protection against DNS leaks. The local
`configs/goreecloud/settings.yml` selects this mode and does not send search
requests without an approved running gateway.

### 2. Hosted server IP masking (optional; remote staging profile)

`configs/goreecloud/server-masked-staging.yml` is a separate opt-in
**Development/Staging-only** template for an independently controlled, remotely
hosted Search server. Providers receive the **server IP**; **do not use it on a
visitor's own laptop, phone or localhost-only personal search deployment**.

Both safeguards must be present before Search can send requests without a
SOCKS gateway:
- `goreecloud.egress_mode: server_masked` plus
  `goreecloud.server_masked_acknowledged: true` in the approved deployment
  profile, and
- `GOREECLOUD_SERVER_MASKED_EGRESS=1` explicitly set in the verified hosting
  environment.

The runtime rejects missing acknowledgements, configured alternative proxies,
unknown modes, insecure TLS options, HTTP and direct per-request transport
overrides. curl's ambient `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY`
proxy inheritance is disabled when the verified server-masked mode is used.
**These configuration checks do not independently prove that a deployment is
remote or that the host IP is unrelated to the user.** The operator must
verify this before setting the acknowledgement. The staging template remains
bound to `127.0.0.1` with no public Identity/rate-limit qualification;
do not publish it to users or reuse it unchanged in Production.

### Tor compatibility (not part of GoreeCloud's privacy requirement)

The upstream `outgoing.using_tor_proxy` verification path remains usable only
when explicitly enabled for another configuration. GoreeCloud's two supported
privacy modes require **no Tor**, no Tor exit check and no Tor installation.
Tor-related historical regression cases are retained as opt-in compatibility
tests, not a product requirement.

## Remaining safeguards and risks

- Query text still goes to the selected approved search providers; no claim
  of encrypted search terms *from* providers or end-to-end anonymity.
- Strip client IP/forwarding, Referer, Origin, tracking and client-hint headers,
  provider cookies and trace IDs. Verify third-party engine adapters don't
  create new identity-bearing headers or direct outbound clients outside this
  guarded network layer.
- Reverse-proxy, hosting-provider, network and exception logs must be audited
  for query and client IP retention. Query-sensitive URLs and error strings
  were redacted in identified application paths, **not all dependencies**.
- Browser result navigation, embedded content, previews, image loading,
  referrer policy and redirects still need full end-user browser verification.
- For public exposure, require verified HTTPS ingress, GoreeCloud Identity,
  Privacy Shield, Valkey/limiter, consent and retention policies, rate limits,
  SSRF protections, compatibility, rollback and actual deployment tests.
- Startpage CAPTCHA, Brave rate limits and Qwant access restrictions may
  affect availability. Never bypass challenges or silently add providers.

## Bounded evidence

At the non-Tor development checkpoint, the laptop's detached checkout
passed **170/170** GoreeCloud regression tests including offline tests of
server-masked acknowledgement, header/cookie stripping, denial on bad
transport/TLS, non-Tor gateway routing and ambient-proxy suppression.
These are **code and contract tests**, not a live hosted visitor/server
separation or DNS/IP packet-leak test. Prior successful live Startpage requests
were made before the mandatory privacy design and do not qualify this change.

**Release remains blocked** until a remote hosted/staging architecture is
verified and an actual synthetic provider search demonstrates that upstream
sees only the server/gateway address, with no client identifiers or local DNS
leaks. GoreeCloud Search remains Development and PR #18 remains Draft.
