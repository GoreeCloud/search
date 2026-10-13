# GoreeCloud Search

**Status: Development source foundation. Not a running or production-accepted Internet metasearch service.**

GoreeCloud Search is intended to be GoreeCloud's free, open-source, self-hostable and privacy-centered web metasearch service. Browser delegates approved web queries to GoreeCloud Search; GoreeCloud Index remains responsible for local/universal discovery. User privacy and first-party authorization must be enforced by the final service.

## Current executable capability

The Python standard-library module `goreecloud_search` implements **offline, provider-neutral result fusion**. It accepts explicitly supplied engine result lists, rejects unsupported URL schemes and credential-bearing links, removes common query-tracking parameters, deduplicates canonical URLs, and ranks cross-engine matches using reciprocal-rank fusion. It neither fetches remote results nor tracks search queries or user identities.

Preview results from local test fixtures:

```bash
python3 -m unittest discover -s tests -v
printf '%s\n' '{"engine_a":[{"title":"Example","url":"https://example.org/?utm_source=test","snippet":"Fixture result"}]}' | python3 -m goreecloud_search
```

The input format is a JSON object mapping stable lowercase engine IDs to arrays of objects containing `title`, `url`, and optional `snippet`. The preview's output is JSON. A preview does not prove Internet engine connectivity.

## Limitations and safety

- No live provider adapters, search APIs, Browser transport integration, query forwarding, Privacy Shield/Identity handoff, operational caching, or deployed service exist in this source milestone.
- Strict input bounds: maximum 16 engines, 50 results per engine, 50 returned results, and 256 KiB CLI input.
- Invalid provider identities, oversized collections, or malformed fields fail closed. Unsafe result URLs are ignored rather than opened/fetched.
- No dependency downloads, external network requests, user queries, cookies, accounts, or credentials are required for the offline preview.
- Additional target-environment integration, security, privacy, accessibility, and Glaze acceptance are mandatory before any service or Stable claim.

See `SPECIFICATIONS.md`, `FEATURES.md`, `BENEFITS.md`, and `COMPETITIVE-OBJECTIVES.md` for versioned scope and objectives.
