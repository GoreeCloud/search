# GoreeCloud Search operator and recovery notes

The following are developer procedures; no production deployment is verified.

## Initializing the local stack

1. Use the isolated development Compose file; inspect its credentials and
   never expose it on the public interface.
2. Configure DATABASE_URL and OPENSEARCH_URL explicitly in your shell.
3. Run goree-search init once to create/update frontier tables.
4. Seed approved HTTPS URLs only. Do not crawl private/intranet sites.
5. Run goree-search crawl --claim 5 --host-delay 5 --max-pages 20.
   A robots preflight runs first, and unknown robot policy results postpone the
   crawl instead of allowing the request. An explicit robots disallow can
   mark the URL excluded and remove older indexed results.
6. Every run leases one due URL per host; discovered links are queued for
   later runs. Seven-day recrawl is due-based, not a scheduled service.
7. Use Uvicorn with --no-access-log and Next.js for the local search UI.

## Manual operator removal

1. Verify the owner request or legitimate grounds, URL and decision.
2. Stop all crawling/indexing workers and verify they are quiescent.
3. Run goree-search remove URL --reason "Verified operator removal".
4. Confirm success. If OpenSearch was unavailable, the SQL tombstone remains
   and the command must be retried until index deletion succeeds.
5. Confirm search-visible absence and exclusion persistence before restarting.
6. Keep a redacted decision record. Do not discard tombstones casually.

A public owner verification and appeals system is not implemented.

## Backup and disaster-recovery rehearsal (not yet executed)

1. Quiesce workers and take consistent PostgreSQL and OpenSearch snapshots.
2. Use authenticated pg_dump -Fc for the frontier; record time and checksum.
3. Use an OpenSearch snapshot repository with tested credentials and retention.
4. Restore to an isolated second environment; never overwrite live originals.
5. Compare frontier records, exclusions, index mapping, document counts and
   representative search queries; test a removal after restore.
6. Record backup/restore duration and rollback evidence.

This is a procedure only. No backup, restore, systemd service or managed
deployment is claimed to exist.
