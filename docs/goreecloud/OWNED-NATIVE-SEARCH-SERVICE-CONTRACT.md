# GoreeCloud Search — owned native service core / Linux candidate (Development)

**Status:** isolated Development candidate with an optional **real, ephemeral systemd lifecycle CI acceptance**; not installed on a managed Linux host, not a supported OS release, and not Seal or Anchor evidence. The existing SearXNG-derived Development fork is a **legacy runtime** and must not remain the complete-product architecture or be relabeled native. This milestone adds a small GoreeCloud-owned runtime boundary that can eventually replace it incrementally. It does **not** change any current VPS, route, deployed container, website, platform product, or user's default search source.

## Real boundary in this milestone

| Responsibility | Source of truth | Included in standalone service artifact? |
| --- | --- | --- |
| Local-owned indexed data, transactional SQLite FTS5, ranking | `native_search/index.py` | Yes |
| Private loopback JSON query API | `native_search/api.py` | Yes |
| Package identity/version | `native_search/__init__.py` | Yes |
| Linux service-only bootstrap | Generated artifact `__main__.py` | Yes |
| Network crawler, publisher policy and corpus admission | `native_search/crawler.py`, explicit external `native_search` CLI | **No** |
| Approved Git corpus/import workflows | `native_search/repo_corpus.py`, explicit external CLI | **No** |
| Existing web search / provider / theme runtime | Legacy SearXNG-derived fork | **No** |
| Platform-specific GUI, GC UI implementation | Future native application projects | **No** |

The artifact contains **only** three allowlisted GoreeCloud-owned modules, a service-only entrypoint and a build manifest. Unlike running `python -m native_search`, its command line has no crawler, seed, URL ingestion, provider choice, public listener or outbound fetch operation. SQLite is opened only against an **existing non-symlink database**; the service cannot quietly create an empty replacement index. Approved, offline ingestion and takedown still occur outside this service with the separate existing native CLI and appropriate filesystem permissions.

### API contract (Development v1)

- Bind: IPv4 `127.0.0.1`, nonprivileged explicitly selected port (default 8789). It cannot be changed to a public interface through the packaged CLI.
- `GET /healthz`: low-information `{"status":"ok","mode":"native-development"}`; **not** a dependency-readiness or security verdict.
- `POST /v1/search`: `Content-Type: application/json`, body at most 4096 bytes, JSON object containing only `query` and optional `limit`. Unicode query must have 1–256 characters, tokenized to 1–16 words; limit 1–20. Result object has `source`, `total_displayed` and `results` with `url`, `title`, `excerpt`, `host`, `indexed_at`, `score`. The response carries no raw query; request logging, CORS and GET search are disabled.
- The server rejects hostile `Host` headers and browser `Origin` submissions, but it has **no production authentication or cross-process authorization**. Loopback is only a transport boundary. Do **not** reverse-proxy it to public/shared clients, embed it in a native app, or equate loopback with device authorization.
- The index is single-process SQLite, not a distributed or multi-writer production index. Index creation/schema initialization can mutate the approved database. Competing writers, backup and migrations are not qualified.

### Deterministic, exact-checkout candidate build

From an **authorized, clean** `GoreeCloud/search` checkout with all edits committed, Python 3.10+ and SQLite FTS5 available:

```sh
python3 -m unittest discover -s tests/native -v
python3 scripts/build_native_linux_service.py \
  --expected-sha "$(git rev-parse HEAD)" \
  --output /tmp/goreecloud-search-native-candidate.pyz
python3 /tmp/goreecloud-search-native-candidate.pyz --help
```

The builder reuses the exact-source guard: authorized origin, 40-character commit matching `HEAD`, clean tree, verified tracked release inputs. It refuses to overwrite an output, symlinks in its three source inputs, missing inputs and source size over budget. The `.pyz` embeds each included SHA-256, repository and source commit. Archive metadata and ordering are normalized for byte-for-byte repeat builds on the **same Python/zlib tooling**. The printed artifact digest is **not** a signature, SBOM, independent attestation, or proof of a deployed artifact. The build itself makes no outbound requests.

### Disposable Linux candidate acceptance (source/CI gate)

The Native Search Development workflow checks out the **actual commit under test** (a pull request's head SHA, never its synthetic merge ref). On Python 3.12 it exercises the same exact-clean-source builder above into a fresh, uninstalled archive under the isolated runner's temporary directory. The bounded `tests/native/native_candidate_runner_smoke.py` then validates the archive member allowlist and embedded source identity, starts its only service in a disposable temporary directory on ephemeral `127.0.0.1`, searches a synthetic approved SQLite fixture, rejects GET-query, hostile Host and browser Origin attempts, checks uncached responses, and terminates the candidate process. It performs no ingestion, network crawling, third-party provider request, service installation, publish, or production mutation.

Separate offline tests reject source-identity mismatch and inherited runtime modules before candidate launch. Where `systemd-analyze` is available, its parser examines a temporary copy of the candidate unit with only absolute fixture paths rebased into an uninstalled directory. That test alone is a **syntax/configuration check**, not real OS lifecycle evidence.

The Python 3.12 hosted-Linux CI job additionally invokes `tests/native/native_systemd_lifecycle_smoke.py` through the actual system manager, with the following explicit boundaries:

1. **Fail closed on environment:** Linux root on an ephemeral **GitHub-hosted** runner, actual PID 1 `systemd` and available `systemctl`/`systemd-analyze` are required. Forked pull requests are excluded from this privileged step; a skipped run is **not** acceptance. No self-hosted runner, VPS, workstation or persistent host is authorized.
2. **Exact artifact and narrowed service:** validate the `.pyz` source commit, repository, module hashes and member allowlist. Copy it, along with synthetic SQLite FTS5 fixture data, into a newly generated private directory under `/run`. Rebase the checked-in unit's existing paths and service identity onto that disposable fixture while retaining its least-privilege/systemd security settings; reject unrecognized required-directive changes or addition of `[Install]`.
3. **Real OS lifecycle:** create the randomly named unit with exclusive creation under `/run/systemd/system`, never `/etc`; use `systemd-analyze verify`, `systemctl daemon-reload`, then exercise start, loopback health readiness, owned fixture POST search, actual non-root process UID/GID, SIGKILL-driven automatic failure restart with a fresh PID, stop with closed listener, absence-of-index start refusal, and recovery after fixture restoration.
4. **Bounded teardown:** stop/reset the disposable unit, unlink only the exclusively created unit and reload systemd; delete the synthetic data and archive on exit. Failure of a required check fails the CI gate and cannot be silently downgraded to a simulated acceptance.

This is an **actual OS-managed unit test in a disposable VM**, not a permanent installation. The unit still has no `[Install]` section and is never enabled, and no service or indexed user data is sent to an external provider. CI success applies only to the exact candidate SHA and runner environment. It does not establish supported distro compatibility, independent proof of egress filters, signed provenance, release/upgrade/rollback, backup/restore, observability, production hardening, or any nine-system integration. Neither local execution of the offline unit tests nor absence of a real hosted-runner result may be labeled a passing OS-managed lifecycle acceptance.

For an isolated local check, prepare an authorized database with the existing `python3 -m native_search import-json --db DB --input APPROVED_FIXTURE`, then run `python3 /tmp/goreecloud-search-native-candidate.pyz --db DB --port 8789` and POST over loopback. Fixture search is not evidence of internet coverage.

The optional `deploy/native-linux/goreecloud-search-native.service` is deliberately **disabled by default**, without an `[Install]` section. It is a reviewable Linux/systemd integration template, **not** an installation script or deployed unit. It requires an independently provisioned unprivileged service user, a verified artifact at `/opt/goreecloud-search-native/search-native.pyz`, an existing approved local index under `/var/lib/goreecloud-search-native/`, compatible CPython/SQLite FTS5, filesystem permissions, local-only exposure, and controlled service management. It specifies `ProtectSystem=strict`, no capabilities, `NoNewPrivileges`, private devices/temp and deny-all IP egress with a loopback exception. The ephemeral acceptance, when actually passed on hosted CI, exercises systemd lifecycle and identity for a temporary, path-rebased instance; it is not evidence for a provisioned managed host or independent egress/resource limits under production workloads.

## Target operating-system and release contract

| Target surface | Implemented now | Required acceptance before any supported-platform claim |
| --- | --- | --- |
| Linux headless native service | Source-pinned Python zipapp, systemd template, offline API/packaging tests and gated ephemeral **real-systemd lifecycle CI scenario** | Hosted CI execution evidence, distro/Python matrix, separately authorized installation/managed-host tests, real egress evaluation, upgrade/rollback, signed release, restore, load test, system observability and security review |
| Linux desktop native application | No | Native OS packaging/window lifecycle, approved GC UI and device acceptance, secure local service communication |
| macOS | No | Native app/service packaging, signing/notarization where applicable, lifecycle, GC UI acceptance and privacy/security tests |
| Windows | No | Native app and managed service implementation, signed installer, service identity/ACLs and OS validation |
| Android | No | Android-native app/background execution and sandbox, supported API levels, GC UI, identity and device tests |
| iOS / iPadOS | No | Native platform app/background rules, signing/distribution, GC UI/identity and representative device tests |

A Python zipapp is a **source artifact**, not by itself a certified native application. A Linux systemd unit is a plausible OS-managed service boundary, still only a candidate. No other platform is silently considered supported.

## Nine Integral Platform Systems: contract assessment, not integration claims

| System | Applicability and current gap |
| --- | --- |
| **GoreeCloud Manager** | Applicable to registration, configuration, start/stop and recovery; no Manager integration. The static systemd template does not transfer administrative authority. |
| **Privacy Shield** | Applicable to query processing, indexed content purpose/retention, takedowns; no authoritative consent/retention integration. Query logging intentionally suppressed. |
| **Wardveil Security** | Applicable to artifacts, runtime isolation, input and network controls; unit hardening and loopback validation are local defenses, **not** Wardveil approval or threat evidence. |
| **Everkeep** | Applicable to SQLite backup/restore, migration, exact rollback; none exercised. |
| **GoreeCloud UI (GC UI)** | Headless service has no present visual controls; any future native user or admin surface must separately implement real platform-native GC UI. Existing legacy web UI is unqualified. |
| **GoreeCloud Mesh** | Applicable to discovery, versioned service contract and health routing; no Mesh registration/discovery integration. |
| **GoreeCloud Identity** | Required before shared or cross-process authorization; no Identity contract and no production app-to-service authentication. |
| **GoreeCloud Policy** | Applicable to corpus sources, permitted query/crawl operations, retention and enforcement; no Policy decision integration. The service cannot crawl by construction. |
| **GoreeCloud Observability** | Applicable to readiness, failures and service health; `/healthz` is narrow liveness only, no trusted metrics/events/evidence routing. |

## Remaining gates and safe next step

1. Review code/CI against an exact clean Development commit; retain build digest and independently inspect archive contents. Capture actual hosted CI lifecycle result and logs; do not mark the new OS test passing from local/offline tests or a skipped fork PR gate.
2. Independently verify deny-all external egress, shutdown, restart, resource limits, file write scope and database integrity in an appropriately approved **disposable** Linux/systemd VM; expand the supported distro/Python matrix. Do not test first on the live VPS.
3. Define signed platform release/install/upgrade/restore/rollback contract; design real OS user-facing app surfaces under GC UI and Identity, rather than adopting an existing complete third-party search engine's product architecture.
4. Implement and test applicable nine-system contracts with named owners, freshness, evidence and failure behavior. Continue separate source quality, legal crawling, privacy and reliability work. Only a later qualified Seal→Anchor transition can mark the Search product Anchor.

Related source evidence: [`NATIVE-SEARCH-FOUNDATION.md`](NATIVE-SEARCH-FOUNDATION.md), [`SOURCE-BASELINE-QUALIFICATION.md`](SOURCE-BASELINE-QUALIFICATION.md), [`GC-UI-CONSUMER-MIGRATION.md`](GC-UI-CONSUMER-MIGRATION.md).
