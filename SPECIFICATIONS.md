# GoreeCloud Search — Development Specifications

## Scope
A first-party, provider-neutral web metasearch service is planned. The current executable component is offline result fusion from caller-supplied results. No live web search, API endpoint, authorization service, or production deployment is established.

## Current source contract
- `fuse_results(sources, limit=10)` takes an engine-id-to-result-list mapping.
- Engine IDs are lowercase alphanumeric with optional underscores/hyphens, at most 32 characters.
- Each item has `title`, `url`, and optional `snippet`; invalid result metadata fails closed.
- Only HTTP(S) result URLs without embedded credentials are eligible; fragments and common marketing-tracking query parameters are removed. This never issues network requests.
- Duplicate canonical URLs are merged across engines. A duplicate within one engine contributes only one vote; reciprocal-rank fusion orders the output deterministically.
- Enforced bounds: 16 engines, 50 rows per engine, 50 output rows, 2048 URL characters, 180 title characters, and 500 snippet characters. CLI input is bounded to 256 KiB.

## Security, privacy, and development gates
Do not infer authorization to send searches, resolve hosts, render untrusted HTML, crawl results, fetch arbitrary URLs, or expose private user data from this pure algorithm. Production must independently satisfy Identity, Privacy Shield, Wardveil Security, Glaze, service authentication, abuse controls, resilience, observability, and deployment acceptance.

## Verification
`python3 -m unittest discover -s tests -v` tests source behavior. CI and live integration require independent evidence.
