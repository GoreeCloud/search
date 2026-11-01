# GoreeCloud Search — Recovery Baseline (2026-11-01)

## Authority and provenance

- Intended public source: `GoreeCloud/search`. The authenticated GitHub API and CLI returned 404 on 2026-11-01 before recovery.
- Recovered source: a **clean local checkout** on the authorized VPS at commit `3ec066fb8efaaa0bc92548949aa1b28ca83e0c42`, dated 2026-10-23.
- GitHub email notifications mention work on 2026-10-27, which was **not** recovered from this checkout. Its code, review status, and merge state are unknown.
- Recovery publication uses a **new root commit** rather than pushing unreviewed historical Git objects. The original local checkout remains unchanged for provenance/recovery.
- Core provenance and licensing: SearXNG upstream foundation; preserve AGPL-3.0-or-later notices, `LICENSE`, `AUTHORS.rst`, `UPSTREAM.md`, and third-party notices. This is not a ground-up implementation.
- The active GoreeCloud UI authority is `GoreeCloud/gc-ui`. Legacy Glaze references are historical evidence only, not current design authority.

## Verified scope of recovered sources

The checkout contains the `searx/` provider/metasearch foundation, `native_search/` development crawler/index/API, `client/` browser assets, `tests/`, `deploy/`, and security/operational documentation. The recovered README describes optional loopback search and limited free-source configurations. Source presence **does not verify** runtime availability, provider success, public deployment, a stable release, or acceptance.

## Safe continuation gates

1. Review the reconstructed public tree for credentials, internal operational metadata, artifacts, and license compliance. A lightweight pattern scan is not exhaustive secret scanning.
2. Run offline unit checks and syntax checks before publication. Perform no unapproved upstream search requests.
3. Restore only a bounded, reviewed source snapshot. Do not mirror all historical refs or automatically deploy.
4. Reconcile 2026-10-24–27 work only if verifiable recovered source becomes available.
5. Migrate legacy Search UI to current GC UI tokens and patterns, with screenshots, accessibility, mobile, and both theme acceptance.
6. Qualify each outbound provider and each API format separately; passing local tests is not production qualification.
7. Update live deployment, monitoring, rollback, and recovery documentation only with tested runtime evidence.

## Security note

A bundled Pexels fallback credential was removed from the recovered development snapshot. The engine now requires successful runtime key discovery or explicit administrator configuration and fails closed when neither is available. Credential-scan results are scoped to the inspected snapshot, not to Git history or live infrastructure.

## Product capability status

The attached founder capability catalog is a **target specification**, not verification that each feature exists in this checkout. Track implemented/partial/planned categories separately in the product plan.
