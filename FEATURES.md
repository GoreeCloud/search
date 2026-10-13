# GoreeCloud Search — Feature Inventory

## Development source in this branch
- Pure Python provider-neutral result fusion and reciprocal-rank ordering.
- Deduplication by canonical HTTP(S) result URL.
- Basic tracking-parameter removal, URI-credential/scheme validation, deterministic ordering, and result-count limits.
- Offline JSON fixture preview CLI and regression suite.
- No external network calls or third-party Python dependencies in this module.

## Not yet implemented
- Live search engine adapters; authenticated Search API; user-facing UI.
- Browser-to-Search delegated requests; Identity/Privacy Shield authorization and policy gates.
- Engine availability assessment, abuse controls, live-service telemetry and recovery.
- Production deployment, user/device interaction validation and Stable acceptance.
