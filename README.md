# GoreeCloud Search

**A brand-new, original GoreeCloud application and service.** This repository is the clean greenfield implementation. It is not a recovery, fork, SearXNG derivative, or continuation of any historical search repository. No historical search code is imported.

**Stage:** new Development foundation (not Stable, deployed, or accepted for release).

## What actually works in this foundation

- An original Python standard-library HTTP application bound **only to 127.0.0.1**.
- Private, manually approved document index using SQLite FTS5, with a bounded, transactional JSONL import.
- A POST-only JSON search endpoint, fixed request limits, strict origin handling, security headers, and minimized logging.
- An original responsive web UI with keyboard-accessible form, loading, empty, and error states; light/dark support and semantic tokens aligned with [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui).
- An original optional provider layer for Brave Search API and a separately managed local SearXNG instance, with per-query user consent, result attribution, deduplication and bounded errors.
- Isolated offline unit, API, consent and static UI tests on a disposable localhost server; no live/billable provider calls.

**Local search remains the default.** All external search integrations are disabled until explicitly configured and chosen by the user for an individual query. No external provider credentials, crawler, AI model, account or telemetry is bundled. This is not a universal web index: the local catalog covers only owner-supplied documents.

## Run locally (Python 3.11+; no third-party dependencies)

```bash
python3 -m goreecloud_search --db /tmp/gc-search-demo.sqlite3 init
python3 -m goreecloud_search --db /tmp/gc-search-demo.sqlite3 import-jsonl --input examples/catalog.jsonl
python3 -m goreecloud_search --db /tmp/gc-search-demo.sqlite3 serve --port 8787
# Open http://127.0.0.1:8787/ on the same device.
```

For the permanent catalog, omit `--db` to use the current user's private state folder. Use a file with one JSON object per line, containing `title`, `description`, `url` (public HTTPS), and optionally `source`. Imports replace the previous catalog atomically; back it up beforehand if needed.

```bash
python3 scripts/verify_greenfield.py
```

## Boundaries and planned next phases

- **No remote exposure:** localhost-only operation. An authenticated edge and independently tested security model are required before any network deployment.
- **Optional egress is off by default:** `GC_SEARCH_EXTERNAL_ENABLED=1` permits configured connectors only. `GC_SEARCH_BRAVE_API_KEY` configures Brave; `GC_SEARCH_SEARXNG_PORT` selects a separately managed loopback SearXNG instance. Only explicit per-query provider selection and `share_query: true` consent trigger calls. Treat provider credentials as secrets; do not paste them into the browser, logs or code. Live adapter compatibility and billing controls are not qualified.
- **No history reuse:** retired PR #1 is not an implementation dependency. Its public historical security alert is tracked separately.
- **UI governance:** [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui) is the sole design-system authority; current CSS semantics are aligned but full integration/visual acceptance remains pending.
- **Next:** qualified live-provider smoke tests with explicit authorization, durable paid-usage caps, real-browser accessibility, richer ranking, native-platform acceptance, and optional Search-to-Open Chat connector.
- **Operational readiness:** backups, structured observability without sensitive queries, packaging, authenticated hosting and staging smoke have not been approved or verified.

For a consented external search, the POST JSON body uses `{"query":"example","providers":["local","brave"],"share_query":true}`; availability is discoverable at `GET /api/providers`. The browser offers the same controls and resets consent after each search. A configured provider can receive the search query, and Brave may incur charges. Keep external access disabled until consent, privacy and billing have been approved.

See [architecture](docs/ARCHITECTURE.md), [connector status](docs/CONNECTOR_STATUS.md), and [development roadmap](docs/ROADMAP.md).

## Licensing

Original GoreeCloud Search code is licensed under Apache-2.0; see `LICENSE`. There are no runtime third-party packages in this phase. The interface uses GoreeCloud UI semantic values as the first-party design reference.
