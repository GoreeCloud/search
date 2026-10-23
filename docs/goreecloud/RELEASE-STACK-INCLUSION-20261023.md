# Search release-line independent PR inclusion — 2026-10-23

**Disposition: HOLD.** This inventory is read-only evidence for deliberate
release-line reconciliation, **not** authority to merge, drop, close, retarget,
deploy, or resolve README conflicts automatically.

## Exact snapshot and scope

The authorized `GoreeCloud/search` GitHub REST open-PR list was read as 39
draft PRs (3 roots to `main`, 36 stacked). The offline audit inspected every
listed head against exact Development commit
`d20cb723d51a85cd01c6e730e96fb202938c761c`; main was
`278fdb45c5688472aa7c547c5b3906c194c2e2b9`. The checkout and Git
objects were read-only and Git origin was the authorized repository. All
snapshot SHA identities and every Git object must be rechecked on rerun.

There are **29 open PR heads whose exact commits are ancestors of
Development**: #3, #5, #6, #8, #9, #10, #14, #16, #17, #22, #23, #24,
#25, #27, #28, #29, #59, #60, #61, #62, #63, #64, #65, #66, #67,
#68, #69, #70, #71.

The remaining **10 heads are not exact ancestors**. For each, the audit scopes
`git cherry` to the common ancestor of its recorded PR base SHA and head,
excludes commits already reachable by exact SHA from Development, and checks
remaining Git patch IDs. All 10 currently have **zero matching patch IDs**;
this does **not** establish that their functionality is absent.

| Open PR | Nonancestor, unmatched Git patch commits | Right-only changed paths | Paths with exact same tip content in Development |
| --- | ---: | ---: | ---: |
| #2 | 1 | 7 | 0 |
| #4 | 1 | 1 | 0 |
| #7 | 11 | 9 | 0 |
| #11 | 8 | 10 | 0 |
| #12 | 1 | 2 | 0 |
| #13 | 1 | 2 | 0 |
| #18 | 71 | 41 | 0 |
| #20 | 10 | 9 | 0 |
| #57 | 3 | 3 | 3 |
| #58 | 2 | 3 | 3 |

This is **109 distinct SHA identities/patch-ID misses** across 10 PRs, not
109 automatically missing features. In particular #57 and #58 have different
commit/patch histories yet **all three right-only changed paths in each PR
match Development's current file contents exactly**; this is positive
file-tip evidence but not proof that every historical behavior, test, or
security requirement has been preserved. Conversely, a different file tip
may be a deliberate subsequent improvement, not a regression. #18 spans
41 differing path tips and 71 unmatched commits: require focused review.

Six recorded PR base SHA edges are stale relative to the current parent head:
**#2, #3, #7, #11, #20, #22**. These are separately disclosed; their drift
must not be mistaken for permission to rewrite ancestry or bypass review.

Main has the known **README-only merge conflict** with stack root #22 and
integrated Development. A human must reconcile README meaning after reviewing
the independent legacy PR work. This audit does not run or apply a merge.

## Reproduction (no Git fetch or modification)

1. Obtain one complete, authorized GitHub REST response from
   `GET /repos/GoreeCloud/search/pulls?state=open&per_page=100`, verifying
   the identity of each included head/base endpoint. Save it **outside**
   the source checkout as an input JSON file.
2. In a **clean** exact-Development checkout of `GoreeCloud/search`, make
   all recorded Git commit/tree/blob objects available beforehand through an
   approved read-only fetch. The audit itself never fetches objects, changes
   refs, writes an index, or changes a worktree.
3. Run:

```sh
python3 scripts/release_stack_inclusion_audit.py \
  --input /path/to/verified-open-prs.json \
  --repo /path/to/clean/search-development-checkout \
  --development-sha d20cb723d51a85cd01c6e730e96fb202938c761c \
  --main-sha 278fdb45c5688472aa7c547c5b3906c194c2e2b9 \
  --expected-pr-count 39 \
  --output /path/to/new-exclusive-release-inclusion-report.json
```

The tool refuses a dirty checkout, a wrong origin/head, missing objects,
incomplete PR counts, unattached stack targets/cycles, excessive data,
ambiguous patch output, and existing output files. Output is always `HOLD`;
the JSON includes exact commit identities, PR-specific unmatched patches,
scope boundaries, right-only changed-file paths, exact file-tip matches, and
recorded base drift. It does not assess code meaning, PR approvals or CI,
release artifact provenance, native platforms, live private ingress, or
Seal/Anchor acceptance.

## Controlled next release action

1. Confirm independent PR owner intent and classify each of the 10 heads as
   **equivalent/replaced**, **still required**, or **deliberately excluded with
   written rationale**. Begin with #18, #20, #7, #11, and high-risk #57/#58.
2. Reproduce/compare tests for security, egress, SQLite recovery, source UX,
   offline fusion and relay shutdown before accepting claimed equivalence.
3. Re-run the graph, inclusion, and main merge-preview audits from fresh,
   exact, authorized GitHub identities; manually reconcile README if approved.
4. Maintain HOLD until all independent review, native platform/security,
   release provenance, required checks, and actual production acceptance
   gates are satisfied. No automated merge or promotion.
