# GoreeCloud Search — Greenfield Architecture v0.1

**Authority:** Brand-new application and service. No historical Search code, recovered implementation, or upstream search engine is a foundation. Canonical design system: [GC UI](https://github.com/GoreeCloud/gc-ui).

## Intentional first scope

User browser → local HTTP boundary → SQLite FTS5 index of explicitly approved JSONL documents.

- **Web:** A self-contained first-party HTML/CSS/JavaScript client using verified GC UI semantic names and base theme values. No remote UI framework or CDN. No persisted search terms.
- **API:** Python 3 standard-library `ThreadingHTTPServer`, bind hard-limited to 127.0.0.1, POST `/api/search` with `{"query": "...", "limit": 12}`, GET `/healthz`. No external calls or implicit cross-origin access.
- **Index:** SQLite FTS5, documents supplied by the user explicitly; no crawler, network fetch, telemetry, personalization or analytics. Each import atomically replaces the catalog.
- **Result contract:** title, description, public HTTPS URL, source. URL input validation and DOM text rendering constrain XSS and local address disclosure.
- **Security:** bounded requests and queries, origin check, restrictive CSP, no user-query logs, no third-party dependencies, optional curator-approved result links. No browser or service remote authentication yet; therefore cannot bind beyond localhost.
- **Deployment:** none. No production, containers, system services, ports beyond ephemeral test loopback or approved local dev server.

## Why this is a foundation, not complete Search

The primary product roadmap includes web, images, videos, news and multi-provider federation, but this foundation has **zero** external adapters. The initial local index validates API, UI, accessibility and privacy contracts without silently exposing search queries.

## Planned provider contract (not implemented)

Each future provider will explicitly declare result category, whether it receives query text, transport, redaction, safe query parameterization, timeout, rate limit, error classifications and allowed hosts. Provider results will pass a validation/normalization boundary and carry source attribution. No provider is enabled before independently reviewed test fixtures and outbound egress authorization.

## Security and validation status

Offline tests cover local indexing, atomic import, URL rejection, query bounds, loopback binding, request origin and JSON handling, and basic security headers. The interface still needs real-browser visual/a11y verification, GC UI package integration, native operating-system acceptance, structured threat modeling, dependency/license checks and release criteria.

Historical recovery PR #1 is closed without merge. It has no implementation dependency. Its historical secret alert is tracked as a **separate** legacy public-repository hygiene item and is not a finding in this new code.
