# GoreeCloud Search — Greenfield Architecture v0.1

**Authority:** Brand-new application and service. No historical Search code, recovered implementation, or upstream search engine is a foundation. Canonical design system: [GC UI](https://github.com/GoreeCloud/gc-ui).

## Intentional first scope

User browser → **strict localhost HTTP boundary** → local SQLite FTS5 index (default), or explicit-consent provider routing → optional Brave HTTPS API / separately managed loopback SearXNG instance (disabled by default).

- **Web:** A self-contained first-party HTML/CSS/JavaScript client using verified GC UI semantic names and base theme values. No remote UI framework or CDN. No persisted search terms.
- **API:** Python 3 standard-library `ThreadingHTTPServer` bound to 127.0.0.1. POST `/api/search` accepts query, limit, optional provider selection and explicit per-query query-sharing consent; GET `/api/providers` shows configured availability and GET `/healthz` reports loopback status. Default search never makes outbound requests. Host, Origin and Sec-Fetch-Site guards prevent cross-site or DNS-rebinding access; early request rejections close keep-alive connections.
- **Index:** SQLite FTS5, documents supplied by the user explicitly; no crawler, network fetch, telemetry, personalization or analytics. Each import atomically replaces the catalog. Original `recovery.py` offers private online SQLite backup snapshots, read-only integrity/record-count verification, and recovery **to a new file only**, never in-place overwrite. This is not a scheduled, offsite or encrypted backup service.
- **Result contract:** title, description, public HTTPS URL, source. URL input validation and DOM text rendering constrain XSS and local address disclosure.
- **Security:** bounded queries and bodies, exact Host checks, Origin/Sec-Fetch-Site protection, restrictive CSP, no query logs, server-only provider secrets, fixed allowed destinations, provider timeouts/response limits and no redirect following. External providers additionally require a global opt-in configuration and per-query user consent. No remote authentication exists; cannot bind beyond localhost.
- **Deployment:** none. No production, containers, system services, ports beyond ephemeral test loopback or approved local dev server.

## Why this is a foundation, not complete Search

The foundation has **two independently developed optional adapters**, not a complete web crawler, search index or production federation service. Brave Search is an external paid/plan-based API; SearXNG is a separate locally operated service that may forward queries. The native SQLite catalog and UI remain functional with external egress off. No provider has passed authorized live qualification.

## Provider contract and next qualification gates

Implemented source contracts select a bounded set of provider IDs, validate fixed transport destinations, apply short timeouts, normalize public HTTPS results and attribute partial failures without raw provider details. Concurrent aggregation deduplicates URLs in source order. A persistent owner-private SQLite ledger now enforces a per-UTC-day **Brave request-count ceiling** before network egress, in addition to short-term pacing, and requires explicit configuration. It serializes cooperating processes using the same file, but is **not** a monetary, provider-account or multi-installation billing cap; this code does not guarantee real provider functionality. See [paid usage controls](PAID_USAGE_CONTROLS.md).

Before permitted live use, verify each provider's published terms, request formats, output settings, key ownership, cost/quotas and privacy disclosures with an owner-approved staging environment. Do not deploy or allow public access without an authenticated edge, audited network policy, and operational controls.

## Security and validation status

Offline tests cover local indexing, atomic import, URL rejection, query bounds, loopback binding, request origin and JSON handling, and basic security headers. The original GTK4 local-only client passed an isolated Linux Xvfb launch/search/result smoke; an isolated real WebKitGTK6 browser smoke validated 390px responsiveness and the result live-status behavior. GTK search input now remains keyboard-focusable while temporarily non-editable during asynchronous searches, and the updated GTK smoke verified its return to editable state. Private SQLite backup/verification/new-file recovery has dedicated offline tests and an authorized Linux CLI round trip. Full keyboard-only/screen-reader/visible UI acceptance, GC UI package integration, broader OS coverage, encrypted scheduled backups, native signed installation, structured threat modeling, dependency/license checks and release gates remain outstanding.

Historical recovery PR #1 is closed without merge. It has no implementation dependency. Its historical secret alert is tracked as a **separate** legacy public-repository hygiene item and is not a finding in this new code.
