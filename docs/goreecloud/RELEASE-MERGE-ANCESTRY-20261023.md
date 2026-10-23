# Search exact ancestry and `main` merge-preview gate

**Date:** 2026-10-23 (America/Chicago)

**Scope:** Governing nonproduction source-line reconciliation, **not** a promotion request

**Status:** HOLD — source inclusion partially verified; README conflict unresolved; Seal/Anchor gates open

The authorized `GoreeCloud` GitHub connection provided fresh PR/branch details. The exact commits were fetched read-only into an isolated GoreeCloud Search worktree and inspected with actual Git three-way merge machinery. The new local inspector is `scripts/release_merge_preview.py`; it does not merge, retarget, commit, push or update any Git reference. It needs a complete *local* object store and refuses implicit partial-clone network fetches. `git merge-tree --write-tree` may create unreachable local tree/blob objects without changing a ref or worktree.

## Verified exact source boundary

| Boundary | Verified value at this audit |
| --- | --- |
| Authorized repository | `GoreeCloud/search` |
| `main` (README-only) | `278fdb45c5688472aa7c547c5b3906c194c2e2b9` |
| Root [PR #22](https://github.com/GoreeCloud/search/pull/22) head | `e4aadf6ddf355f1f6c98de142b111da9b1fbcd79`, open draft, `dirty`, `mergeable=false` |
| Integrated [PR #71](https://github.com/GoreeCloud/search/pull/71) head | `0ff2a637b56f0dca4f0f9c17a919d3c2b3087be4`, open draft; targets stacked PR #70, **not** `main` |
| Actual common Git ancestor | `abbba851d6bb35a2e7df2f03f798ab3e6f9fc5d5` |
| Root #22 head is an ancestor of integrated Development | **Yes**, verified by `git merge-base --is-ancestor` |
| Exact main-side paths changed since common ancestor | Only `README.md` |
| Exact PR #22 / `main` merge preview | Conflict: `README.md` only |
| Exact integrated Development / `main` merge preview | Conflict: `README.md` only |
| Paths changed in Development after root #22 | 172 paths, **not** proof that every independent stacked PR patch is included |

Both merge previews failed to resolve the README three-way conflict; the resulting conflict trees are Git objects for inspection, not valid release candidates. The unmerged root (#22) contains historically inaccurate active descriptions, including the old three-provider Development lineup and former UI authority. The current Development README more accurately describes the free-first seven-family configuration, direct-HTTPS upstream disclosure, legacy Tor profile boundary, different deployed-image source, and the lack of Seal/Anchor. The `main` README carries a distinct source-of-truth warning and release-governance pointers; blindly keeping either side in full would preserve false claims or drop useful audit context.

## Safe README reconciliation constraints

When a separate promotion task is explicitly approved **after** release gates, a reviewed, isolated conflict-resolution candidate must:

1. Preserve `main`'s material safety warnings, references to GitHub release/ingress/security issues, and distinction between source evidence and a deployed service—updating time-bound wording that would become false if `main` acquires runnable code.
2. Preserve Development's verified provider-selection contract, user query/IP disclosures, historical profile distinctions, opt-in native index limits, and current GC UI authority, avoiding legacy provider-count/UI claims from root #22.
3. Retain legally required upstream SearXNG/AGPL attribution and the historical provenance boundary, while never describing the inherited complete-product architecture as an Anchor-qualified GoreeCloud-owned native application.
4. Require an explicit file-level comparison of the candidate merge tree to both exact parents, preserving **all** independently intended source additions and assessing PR #2/#7 and any other unmerged work. A successful merge-tree exit code alone cannot prove semantic or patch preservation.
5. Revalidate the resulting exact candidate using required source, functional, security, native-platform, provenance, private-ingress, GC UI, rollback, and release gates. No automatic retarget, history rewrite, `main` merge, production deployment, Seal freeze or Anchor designation follows from this report.

## Repeatable nonpromotion diagnostic

Run only from a complete, **clean**, authorized GoreeCloud Search checkout at the expected exact Development head. Obtain all three current SHAs from the approved GoreeCloud GitHub connection; don't reuse these dated values after source changes.

```sh
python3 scripts/release_merge_preview.py \
  --main-sha 278fdb45c5688472aa7c547c5b3906c194c2e2b9 \
  --root-pr-sha e4aadf6ddf355f1f6c98de142b111da9b1fbcd79 \
  --development-sha 0ff2a637b56f0dca4f0f9c17a919d3c2b3087be4 \
  --output /path/to/new-merge-preview.json
```

The program fails closed when an expected object or Git origin is invalid, source checkout is dirty or wrong, root is not an ancestor, merge bases differ, or Git can't provide unambiguous conflict output. It checks *actual Git commit ancestry and three-way conflicts* rather than relying only on PR-recorded base SHA. The output includes source identities, tree preview OIDs, paths changed on `main`, count of Development paths since the stack root, and explicit remaining blockers. It cannot verify README meaning, independent PR patch inclusion, repository protections, external reviews, signed artifact provenance, live deployment, runtime security, or Anchor acceptance. **Every valid report deliberately returns `HOLD_NO_PROMOTION_OR_AUTOMATIC_CONFLICT_RESOLUTION`, even when Git reports a clean mechanical merge.**

Synthetic regression tests (including real temporary-repository merges) can be run with:

```sh
python3 -m unittest discover -s tests/goreecloud -p test_release_merge_preview.py -v
```

This is dated Development evidence, not a continuously updated GitHub status. Reverify actual SHAs, PR state and release requirements before any future decision. `main`, live VPS, DNS, Caddy, NetBird, the Search container and current user traffic were not touched by this audit.

Related: [`RELEASE-LINE-CONSOLIDATION-20261023.md`](RELEASE-LINE-CONSOLIDATION-20261023.md) and [`SOURCE-BASELINE-QUALIFICATION.md`](SOURCE-BASELINE-QUALIFICATION.md).
