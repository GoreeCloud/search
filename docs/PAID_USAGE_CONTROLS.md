# GoreeCloud Search — Optional Brave API request ceiling

**Status:** First-party Development safeguard, **not** a provider contract, monetary billing cap, or authorization to use a paid service. Brave and SearXNG remain disabled by default.

## Design

Brave calls are permitted only when **all** of the following hold:

1. Global outbound opt-in is configured (`GC_SEARCH_EXTERNAL_ENABLED=1`).
2. A server-side Brave API credential is supplied (`GC_SEARCH_BRAVE_API_KEY`).
3. A positive daily per-installation request ceiling is configured (`GC_SEARCH_BRAVE_DAILY_CAP`, an integer from 1 to 10,000).
4. The request explicitly selects Brave and includes `share_query: true`; the browser resets this consent after each search.
5. The existing short-term in-process pacing gate permits the request **and** the owner-private SQLite ledger atomically reserves one counted request before opening the API connection.

Without an explicit cap, GET `/api/providers` reports Brave unavailable, even if the service and key are configured. Local search and separately operated local SearXNG are unaffected.

## Optional configuration reference (not a deployment instruction)

- `GC_SEARCH_BRAVE_DAILY_CAP`: maximum attempted Brave requests in one **UTC date** for this installation. No value means Brave unavailable. The configured value must use 1–5 ASCII decimal digits, without zero-padding, and be within 1–10,000; oversized malformed values fail closed before integer parsing.
- `GC_SEARCH_BRAVE_BUDGET_DB`: optional absolute path to a private, local SQLite ledger. Default with a valid positive cap: `~/.local/state/goreecloud/search-brave-budget.sqlite3`.
- `GC_SEARCH_SEARXNG_PORT`: the optional locally managed SearXNG port must be 1–5 canonical ASCII digits representing 1–65,535. Extremely long, Unicode-numeric, out-of-range and zero-padded ports are rejected as configuration errors before any outbound connection.

- `GC_SEARCH_EXTERNAL_ENABLED` and `GC_SEARCH_BRAVE_API_KEY`: required alongside source selection and per-query consent.

The budget directory must be owner-only (`0700`), and the SQLite file must be owner-only (`0600`). Existing symlinked files/directories (including non-immediate ancestor directories), corrupt files, insecure permissions and ledger errors fail closed. This uses filesystem checks before ledger access; it is not protection against an attacker with the same user privileges swapping paths concurrently. State contains **only UTC dates and integer request counts**, not search terms or credentials. Attempted requests count even if the provider returns an error; ambiguous failures are not refunded.

A SQLite `BEGIN IMMEDIATE` transaction serializes requests from concurrent threads and cooperating processes **on the same ledger**. The limit is **local to that ledger**, not account-wide. Multiple machines, separate ledgers, external API usage, and rate/plan changes are not covered. A configured limit is **not a guarantee of zero charge or a monetary spending limit**.

## Test evidence and release criteria

`tests/test_request_budget.py` covers request ceilings across reopen, concurrent threads and processes, UTC-day boundaries, private file permissions, rejected symlinks, corrupt ledger data, invalid caps, provider availability, pre-transport reservations and blocked transport after exhaustion. `scripts/verify_greenfield.py` requires this suite and the existing app suites with zero skips. Provider response JSON parsing is also strict: replies containing duplicate field names at any object depth or nonstandard numeric constants (`NaN`, `Infinity`) fail closed as a generic provider failure without exposing response internals. Three additional transport-mock tests enforce the rule. This is distinct from validating provider authenticity, provider pricing or account-wide spending controls.

The provider HTTP transport tests are mocked; **no live/billable request was executed**.

**Do not enable paid egress** before the legitimate account owner approves keys, pricing, scope and daily usage; verifies the provider's real-time plan controls and account-level hard spending limits where supported; reviews privacy and logging disclosures; qualifies outbound transport privately; and decides how to monitor usage across devices. This local safeguard reduces a specific failure mode, but cannot replace those gates.

### Security limitations

The ledger operates under a trusted local user account and private directory. It does not defend against a hostile process running with the **same user permissions** modifying the ledger or clock, multiple installations that fail to share state, or provider-side billing semantics. Time is based on the local system UTC clock. Do not label this implementation a bank-grade, cross-device, or monetary budget.
