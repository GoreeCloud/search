# GoreeCloud Search — offline tracker rule initialization

**Scope:** Development source only; not a live provider/release qualification.

The default SearXNG tracker URL remover downloads ClearURLs rules from
third-party endpoints when it initializes. GoreeCloud Search must not create
this unapproved startup egress dependency, even when optional privacy flags
are overridden. For a nonempty `goreecloud` settings namespace, the existing
tracker-removal plugin instead loads a fixed, locally audited rule.

The offline rule strips only known advertising/analytics query keys:
`utm_*`, `fbclid`, `gclid`, `msclkid`, `igshid`, `ttclid`,
`twclid`, `mc_cid` and `mc_eid`. Other query keys remain intact.
Unlike online ClearURLs rule downloads, this is **not** comprehensive tracker
protection, and it cannot prevent every redirection/tracking technique.

An upgrade from a prior SearXNG/GoreeCloud image may leave remote ClearURLs
rules in an existing SQLite cache and a prior `tracker_patterns loaded=OK`
marker. GoreeCloud Search now bypasses that cache for tracker cleanup
completely: both plugin initialization and rule consumption use only the
built-in rule. Old cached entries are not interpreted, fetched, or rewritten
on the branded path. Existing cache rows may remain on disk until their normal
lifecycle expires; this does not assert secure erasure.

The original upstream SearXNG behavior is preserved in instances without a
GoreeCloud settings namespace. Cleanup debug logs no longer contain result
hosts, query parameter names/values, or raw URL strings.

Validation: use `tests/goreecloud/test_offline_tracker_rules.py` on a
dependency-installed development checkout. The regression mocks remote
download calls; tests do **not** send queries, access providers, contact Tor,
or change the running private VPS.

**Release boundary:** offline rules do not resolve provider HTTP 403/429,
CAPTCHA, source licensing, DNS rebinding, private-network egress or the
unqualified Development-to-Stable release gate.
