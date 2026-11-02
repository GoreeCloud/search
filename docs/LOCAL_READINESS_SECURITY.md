# GoreeCloud Search — Local readiness and strict HTTP contracts

**Scope:** Original first-party Search development service, bound to 127.0.0.1 only. Draft [PR #2](https://github.com/GoreeCloud/search/pull/2); not merged or deployed.

## Distinguishing liveness and readiness

- `GET /healthz` reports **process liveness**. A running server may return HTTP 200 even if its SQLite catalog has been removed or rendered unreadable. This is intentional.
- `GET /readyz` reports **private local catalog readiness**. It runs the same owner-private file, SQLite integrity and Search-schema checks used by `verify-backup`. Returns 200 `{"status":"ready","scope":"local-catalog"}` if usable, otherwise 503 `{"status":"unavailable","scope":"local-catalog"}`. No document count, query, path or credential is disclosed.
- Both paths require the exact `127.0.0.1:port` Host and send `Cache-Control: no-store`. No endpoint is accessible via an authenticated remote edge or publicly hosted service.
- Browser UI performs a cacheless, credential-free `/readyz` check on initial load. If the catalog is unavailable, it announces this in the existing accessible status region. It does not disable controls, call external providers, or overwrite an in-progress search or newer result.

## Strict HTTP JSON consent safety

The POST-only `/api/search` endpoint uses an 8 KiB body limit and now fails closed on:

- Duplicate JSON field names **at any object depth**, including duplicated provider selection or query-sharing consent.
- Nonstandard JSON number literals such as NaN and Infinity.
- Repeated Content-Type fields or requests with Transfer-Encoding present, including an empty header field.
- Early request rejection with unread body, where the service returns a connection-close signal to avoid HTTP/1.1 request desynchronization.

GET endpoints also **reject declared unread bodies**: nonzero or malformed `Content-Length`, repeated length fields, and any `Transfer-Encoding`. Rejections close the HTTP/1.1 connection instead of treating leftover bytes as another request. Zero-length GETs and ordinary requests without body headers continue to work. Three loopback integration regressions verify these protections without sending request bodies or invoking a provider.

The handlers produce bounded generic responses and do not log search terms or provider credentials. All external providers remain disabled by default and still require explicit server setup and per-query opt-in.

## Browser single-flight query and consent guard

The web form now guards against **overlapping POST searches** independently of the submit button's disabled state. If a query is in progress, another submission is ignored before provider selection and HTTP request creation. After success or error, the guard is cleared in `finally`, the provider reverts to local, and per-query external sharing consent is unchecked. This limits accidental duplicate consented queries caused by repeated Enter or programmatic submits; it does **not** guarantee that an external provider never bills a request, eliminate deliberate sequential re-submissions, or replace the separate durable Brave per-ledger daily limit.

Two new offline UI contract checks enforce guard ordering and reset behavior. An authorized Linux WebKitGTK 6.0/Xvfb integration smoke of the **real browser UI** first performed a local HTTP search, then replaced only the test page's `fetch("/api/search")` in the isolated renderer with an unresolved synthetic promise. Two immediate consented Brave form submissions resulted in **exactly one mocked request**, with explicit `share_query: true` in the intercepted body; after resolving it, busy state cleared and the provider/consent returned to local/unchecked. The test made **no actual Brave or external API request**. This is functional browser acceptance, not account-level billing verification or screen-reader testing.

## Validation evidence and remaining release gates

`tests/test_http_strict_json.py` runs six live localhost request-level regression cases without third-party egress. `tests/test_readiness.py` covers working, missing, and permission-denied catalog states and checks that untrusted Host headers never read the index. The two additional browser UI contract checks verify that readiness remains advisory and cannot replace an active search status.

Run `python3 scripts/verify_greenfield.py` and `node --check web/app.js` to validate in an authorized development checkout. Consult the current draft PR head and GitHub Actions state before quoting a passing number.

The separate experimental `scripts/smoke_atspi_native.py` **has not passed** in the isolated Linux Xvfb/DBus environment: the AT-SPI registry started but did not expose the expected native GTK4 client labels in its application tree. This is a **blocker**, not a screen-reader acceptance result. Orca speech behavior, full assistive technology, real keyboard traversal and cross-platform UI review remain unverified. Do not declare Stable/Seal based on browser keyboard or static contrast checks.
