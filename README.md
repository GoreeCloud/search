# GoreeCloud Search

**A brand-new, original GoreeCloud application and service.** This repository is the clean greenfield implementation. It is not a recovery, fork, SearXNG derivative, or continuation of any historical search repository. No historical search code is imported.

**Stage:** new Development foundation (not Stable, deployed, or accepted for release).

## What actually works in this foundation

- An original Python standard-library HTTP application bound **only to 127.0.0.1**.
- Private, manually approved document index using SQLite FTS5, with a bounded, transactional JSONL import.
- A POST-only JSON search endpoint, fixed request limits, strict origin handling, security headers, and minimized logging.
- An original responsive web UI with keyboard-accessible form, loading, empty, and error states; light/dark support and semantic tokens aligned with [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui).
- Isolated offline unit/API tests on a disposable localhost server.

No external search engines, crawlers, AI models, accounts, telemetry, or third-party query disclosure are included. No universal web search is promised. This phase indexes only documents deliberately provided by the owner and does not fetch the linked pages.

## Run locally (Python 3.11+; no third-party dependencies)

```bash
python3 -m goreecloud_search --db /tmp/gc-search-demo.sqlite3 init
python3 -m goreecloud_search --db /tmp/gc-search-demo.sqlite3 import-jsonl --input examples/catalog.jsonl
python3 -m goreecloud_search --db /tmp/gc-search-demo.sqlite3 serve --port 8787
# Open http://127.0.0.1:8787/ on the same device.
```

For the permanent catalog, omit `--db` to use the current user's private state folder. Use a file with one JSON object per line, containing `title`, `description`, `url` (public HTTPS), and optionally `source`. Imports replace the previous catalog atomically; back it up beforehand if needed.

```bash
python3 -m unittest discover -s tests -v
```

## Boundaries and planned next phases

- **No remote exposure:** localhost-only operation. An authenticated edge and independently tested security model are required before any network deployment.
- **No external provider calls:** each future federated adapter requires separate privacy and reliability review; the current API is local-index-only.
- **No history reuse:** retired PR #1 is not an implementation dependency. Its public historical security alert is tracked separately.
- **UI governance:** [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui) is the sole design-system authority; current CSS semantics are aligned but full integration/visual acceptance remains pending.
- **Next:** provider interface specification, explicit consent/egress contract, ranking and deduplication, accessibility and native-platform acceptance, optional Search-to-Open Chat connector.
- **Operational readiness:** backups, structured observability without sensitive queries, packaging, authenticated hosting and staging smoke have not been approved or verified.

See [architecture](docs/ARCHITECTURE.md) and [development roadmap](docs/ROADMAP.md).

## Licensing

Original GoreeCloud Search code is licensed under Apache-2.0; see `LICENSE`. There are no runtime third-party packages in this phase. The interface uses GoreeCloud UI semantic values as the first-party design reference.
