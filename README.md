# GoreeCloud Search

**A brand-new, original GoreeCloud application and service.** This repository is the clean greenfield implementation. It is not a recovery, fork, SearXNG derivative, or continuation of any historical search repository. No historical search code is imported.

**Stage:** new Development foundation (not Stable, deployed, or accepted for release).

## What actually works in this foundation

- An original Python standard-library HTTP application bound **only to 127.0.0.1**.
- Private, manually approved document index using SQLite FTS5, with a bounded, transactional JSONL import. Local and optional remote result links share one original [public HTTPS navigation policy](docs/PUBLIC_LINK_POLICY.md) to reject malformed and local-network targets before display.
- A POST-only JSON search endpoint, fixed request limits, strict origin handling, security headers, and minimized logging.
- An original responsive web UI with keyboard-accessible form, loading, empty, and error states; light/dark support and semantic tokens aligned with [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui).
- An independent **optional native GTK4 desktop client** for the private SQLite index, including native search entry, result list, non-blocking searches, and safe HTTPS links. It uses no search provider, HTTP server, or browser runtime; real GTK4 desktop rendering has not yet been accepted.
- An original optional provider layer for Brave Search API and a separately managed local SearXNG instance, with per-query user consent, result attribution, deduplication and bounded errors.
- Isolated offline unit, API, consent and static UI tests on a disposable localhost server; no live/billable provider calls.

**Local search remains the default.** All external search integrations are disabled until explicitly configured and chosen by the user for an individual query. No external provider credentials, crawler, AI model, account or telemetry is bundled. This is not a universal web index: the local catalog covers only owner-supplied documents.

## Run locally (Python 3.11+; no third-party dependencies)

```bash
# Create an owner-private directory; the public /tmp directory is not accepted
# as the direct parent of a sensitive SQLite index.
GC_SEARCH_DEMO_DIR="$(mktemp -d /tmp/gc-search-demo.XXXXXXXX)"
python3 -m goreecloud_search --db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3" init
python3 -m goreecloud_search --db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3" import-jsonl --input examples/catalog.jsonl
python3 -m goreecloud_search --db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3" serve --port 8787
# Open http://127.0.0.1:8787/ on the same device.
```

### Optional native GTK4 desktop

On a Linux desktop with GTK4 and PyGObject installed from the operating system's trusted package repository (for example, packages `python3-gi` and `gir1.2-gtk-4.0` on supported Debian/Ubuntu environments), initialize/import the catalog as above, then run:

```bash
# Use the same GC_SEARCH_DEMO_DIR from the preceding setup in this shell.
python3 -m goreecloud_search.native --db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3"
```

The directory created with `mktemp -d` is disposable development state. Treat its catalog as private and remove it manually when no longer needed; these commands never erase it automatically.

The native client reads the private index **directly**; it does not start a web server or use Brave/SearXNG. The UI follows GC UI hierarchy and spacing principles using system GTK4 widgets; visual parity, keyboard/assistive-technology and packaging acceptance are still pending. The Python service and test suite do not require GTK.

### Non-installing native development archive

The first-party `scripts/package_native.py` builds a **reproducible, source-only** GTK4 development `.tar.gz` archive with a portable launcher and desktop-entry template. It does not run installers, update PATH, change desktop settings, deploy, sign, or activate external sources. From a trusted checkout:

```bash
python3 scripts/package_native.py --output /tmp/goreecloud-search-native-dev.tar.gz
python3 scripts/package_native.py --verify /tmp/goreecloud-search-native-dev.tar.gz
```

See [native archive validation](docs/NATIVE_ARCHIVE_VALIDATION.md) for its SHA-256 file manifest, bounded read-only verifier, contents, and remaining release requirements. Self-contained hashes detect inconsistencies but **cannot authenticate the publisher or replace a release signature**. This is **not** a released Linux installer.


For the permanent catalog, omit `--db` to use the current user's private state folder. Use a file with one JSON object per line, containing `title`, `description`, `url` (public HTTPS), and optionally `source`. Imports replace the previous catalog atomically; back it up beforehand if needed.

### Private local backup and recovery

The original standard-library recovery helpers make **non-destructive SQLite snapshots** and verify their integrity. The destination must not already exist and must be inside an owner-private directory. No command overwrites the active index.

```bash
python3 -m goreecloud_search --db /absolute/private/catalog.sqlite3 backup --output /absolute/private/backups/snapshot.sqlite3
python3 -m goreecloud_search verify-backup --input /absolute/private/backups/snapshot.sqlite3
python3 -m goreecloud_search restore-copy --input /absolute/private/backups/snapshot.sqlite3 --output /absolute/private/recovered.sqlite3
```

These are private local development copies, **not** scheduled/offsite encrypted backups or a production recovery guarantee. See [catalog recovery and safety](docs/CATALOG_BACKUP_RECOVERY.md).

```bash
python3 scripts/verify_greenfield.py
```

## Boundaries and planned next phases

- **No remote exposure:** localhost-only operation. An authenticated edge and independently tested security model are required before any network deployment.
- **Local operational status:** `GET /healthz` reports server liveness; `GET /readyz` checks that the private SQLite index is usable without exposing catalog contents. The browser displays a non-blocking readiness notice if the index is unavailable. Strict POST JSON parsing refuses repeated fields, including duplicated consent. See [readiness and protocol notes](docs/LOCAL_READINESS_SECURITY.md).
- **Optional egress is off by default:** `GC_SEARCH_EXTERNAL_ENABLED=1` permits configured connectors only. `GC_SEARCH_BRAVE_API_KEY` configures Brave but is insufficient on its own: `GC_SEARCH_BRAVE_DAILY_CAP` must also explicitly set a positive, local UTC-day request ceiling (1–10,000); optionally choose an absolute `GC_SEARCH_BRAVE_BUDGET_DB` for a private SQLite ledger (otherwise `~/.local/state/goreecloud/search-brave-budget.sqlite3` is used). `GC_SEARCH_SEARXNG_PORT` selects a separately managed loopback SearXNG instance. Only explicit per-query provider selection and `share_query: true` consent trigger calls. Treat provider credentials as secrets; do not paste them into the browser, logs or code. This ledger counts attempted requests across local restarts/processes sharing one file, but is **not** an account-wide billing or money cap. Live adapter compatibility, provider billing, and account-level usage controls are not qualified. Read [paid usage controls](docs/PAID_USAGE_CONTROLS.md) before any approved opt-in.
- **No history reuse:** retired PR #1 is not an implementation dependency. Its public historical security alert is tracked separately.
- **UI governance:** [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui) is the sole design-system authority; current CSS semantics are aligned but full integration/visual acceptance remains pending.
- **Next:** qualified live-provider smoke tests with explicit authorization, durable paid-usage caps, real-browser accessibility, richer ranking, native-platform acceptance, and optional Search-to-Open Chat connector.
- **Operational readiness:** backups, structured observability without sensitive queries, packaging, authenticated hosting and staging smoke have not been approved or verified.

For a consented external search, the POST JSON body uses `{"query":"example","providers":["local","brave"],"share_query":true}`; availability is discoverable at `GET /api/providers`. The browser offers the same controls and resets consent after each search. A configured provider can receive the search query, and Brave may incur charges. Keep external access disabled until consent, privacy and billing have been approved.

See [architecture](docs/ARCHITECTURE.md), [connector status](docs/CONNECTOR_STATUS.md), [development roadmap](docs/ROADMAP.md), [XTest keyboard evidence](docs/KEYBOARD_ACCESSIBILITY_VALIDATION.md), [GC UI contrast checks](docs/ACCESSIBILITY_CONTRAST.md), [local readiness and HTTP security](docs/LOCAL_READINESS_SECURITY.md), and [historical secret-alert triage](docs/LEGACY_SECRET_ALERT_TRIAGE.md).

## Licensing

Original GoreeCloud Search code is licensed under Apache-2.0; see `LICENSE`. There are no runtime third-party packages in this phase. The interface uses GoreeCloud UI semantic values as the first-party design reference.
