# Owned native Search index — disposable backup/restore probe

**Status: Development-only source and synthetic-fixture acceptance. Not an Everkeep integration or a tested live-service restore.**

The GoreeCloud-owned `native_search` SQLite FTS5 index now has an explicit, bounded recovery exercise implemented by `scripts/native_index_recovery_probe.py`. The tool only reads its source, creates **two new** output databases (a snapshot and a restored probe), verifies SQLite structural consistency and the FTS5 external-content index, and reports SHA-256 digests and document count. It never stops a service, overwrites an existing destination, changes an existing index, or contacts a network endpoint.

## Reproduce on a synthetic approved fixture

Use an isolated working directory and generate a synthetic index with the existing owned index/CLI first. The snapshot command requires three different explicit paths; neither output may already exist:

```bash
python3 -m unittest discover -s tests/native -p test_index_recovery_probe.py -v
python3 scripts/native_index_recovery_probe.py \
  --source /path/to/synthetic-index.db \
  --backup /path/to/new-backup.db \
  --restore-probe /path/to/new-restored-probe.db
```

The command checks a valid SQLite header, owned `pages`/`pages_fts` schema and required triggers, complete database integrity, matching restored page count, and FTS5 index integrity. It uses SQLite's backup API for a transactional copy and separately restores that copy; live concurrent-write behavior has **not** been qualified. All generated files are exclusive-create with owner-only mode; symlink paths, malformed/corrupt sources, empty or oversized sources, and pre-existing destinations fail closed. An interrupted run is not recovery acceptance; verify or securely dispose of temporary outputs under the applicable data-handling policy.

The result contains **no document text, URLs, search queries or local source path**. Its reported digests are local integrity evidence, not signatures or attestations. A synthetic fixture test is not evidence of operational recovery of any NetBird/VPS or deployed Search index.

## Open production gates

- **Everkeep:** Versioned integration, approved storage destination, backups at defined retention/availability points, encryption and authorized access remain open.
- **Live consistency:** Continuous writes, cross-process migrations, source permissions and full outage/interruption handling have not been exercised with the actual managed service.
- **Restore:** A disposable local copy is not proof of production database or OS service restore, full application search behavior, service startup, rollback, or recovery time objective.
- **Seal/Anchor:** Signed, traceable release artifacts, target-runtime installation, nine-system contracts, real restoration drills, audit evidence and acceptance remain separately blocking.

Do not invoke this probe against a live, private, or personally sensitive index merely to generate evidence without an approved data-handling/recovery exercise. The provided CI tests use synthetic fixture records exclusively and do not touch the running VPS.
