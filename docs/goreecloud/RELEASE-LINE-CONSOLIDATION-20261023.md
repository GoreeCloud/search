# Search release-line consolidation: controlled inventory and decision gate

**Date:** 2026-10-23 (America/Chicago)

**Scope:** GoreeCloud/Search, read-only PR relationship audit and local Development-line planning

**Authority:** GoreeCloud master operating instructions v1.27 and GoreeCloud release lifecycle (Seed → Lab → Forge → Weave → Seal → Anchor → Sunset → Archive)
**Not an Anchor or Seal certification.** Development is an environment, not a lifecycle stage.

## Exact source and live-line evidence

- At this audit snapshot, the integrated **Development** head represented by PR #71 was commit `871f2e5e95143e806d62746eeecf4d168de2fe2b` on `feature/search-working-free-sources-20261020`. Subsequent Development merges move that head; this is a dated observation, not the current promotion candidate.
- PR #71 targets the PR #70 stack branch `security/search-free-readonly-release-gate-20261020`; its **base is not `main`**.
- `main` was observed at `278fdb45c5688472aa7c547c5b3906c194c2e2b9` (a README-only line, not demonstrated to contain Development functionality).
- PR #22 is one of the `main`-targeting roots, at `e4aadf6ddf355f1f6c98de142b111da9b1fbcd79`; GitHub reports it `mergeable=false`, `mergeable_state=dirty`. This is a present conflict, not an invitation to force it through.

The authorized GoreeCloud GitHub connection was queried on 2026-10-23 with `GET https://api.github.com/repos/GoreeCloud/search/pulls?state=open&per_page=100` and individual PR detail GETs for #22/#71. At that read:

| Evidence | Observed |
| --- | ---: |
| Open PRs | 39 |
| Open drafts | 39 |
| Directly target `main` | 3: #2, #7, #22 |
| Target another PR/stack branch | 36 |
| PR target branch SHA mismatches, stacked edges | 3 |
| PR recorded `main` base SHA different from observed `main` | 3 |

The new checker was executed against all **39 actual authorized PR records** (reduced to its required fields in memory, without persisting a credential or export). It found **39/39 paths back to `main`, no missing parent PR branches, and no graph cycles**, but six recorded-base/current-target SHA mismatches. The 20-PR integrated Development path is:

`#71 → #70 → #69 → #68 → #67 → #66 → #65 → #64 → #63 → #62 → #61 → #60 → #59 → #29 → #28 → #27 → #25 → #24 → #23 → #22 → main`

Thus the integrated Development lineage currently depends on the root **#22**, which is reported dirty against `main`; the existence of a complete graph path does not make the promotion path mergeable.

An earlier working baseline listed 40 open PRs, 39 drafts, and 37 stacked. That baseline is **superseded as a current count**: #89 merged and is no longer open. Do not use historical counts for a release decision. Refresh before action.

### Recorded-base SHA versus current target-branch head

These are mismatches in GitHub PR records, **not proof of code loss or an actual merge conflict**. A PR's recorded base SHA is not a substitute for a fresh ancestry and patch analysis.

| Child | Target parent | PR recorded base SHA | Current target parent head SHA |
| --- | --- | --- | --- |
| #20 | #18 | `92adcc48c371af6ac5deb3ec60ffa3635f760980` | `80d83cc16ab96d2e8b3fa27cd26b27c99c567361` |
| #11 | #10 | `36b13551e7d672c0ffb4439494687b849f66c379` | `db75d0921f356f1a876f3a0fcbdbe10abc3a17c5` |
| #3 | #2 | `e79495d735919c9741fcfaeca6839e33f99af6fc` | `3f039fe368045a59fa945cd7bbd28e9393721212` |

The three `main`-targeting roots #2, #7, #22 each record `abbba851d6bb35a2e7df2f03f798ab3e6f9fc5d5` as the PR base SHA, which differs from the observed current `main` SHA above.

## Read-only, reproducible graph check

The stdlib-only `scripts/release_pr_graph_inventory.py` **does not connect to GitHub and never changes a PR or a Git ref**. Supply a complete authorized GitHub REST JSON array from the `/pulls?state=open&per_page=100` response. The input must cover all open PRs (the tool refuses exactly 100 entries to prevent trusting a possibly truncated first page), with native head/base repo, ref, SHA, state, draft, and number fields. Do not store an access token in the export.

```bash
python3 scripts/release_pr_graph_inventory.py \
  --input /path/to/authorized-open-prs.json \
  --expected-dev-sha 871f2e5e95143e806d62746eeecf4d168de2fe2b \
  --expected-main-sha 278fdb45c5688472aa7c547c5b3906c194c2e2b9 \
  --output /path/to/new-release-pr-graph-report.json
```

The output must be a **new** path (exclusive creation; no overwrites). Omitting `--output` prints JSON. It validates the exact #71 Development head, checks branch/repository identity, duplicate or ambiguous refs, direct-main roots, missing parents, path-to-main, cycle members, and recorded-base SHA differences. Sort order is deterministic. A malformed, foreign, closed, incomplete, too-large, or unverified source fails closed. Run the offline unit tests with:

```bash
python3 -m unittest discover -s tests/goreecloud \
  -p test_release_pr_graph_inventory.py -v
```

Every emitted report deliberately says `release_decision=BLOCKED_NOT_QUALIFIED`. That is a scope limitation: PR relationships alone **cannot certify** current mergeability, commit ancestry, branch protection, required checks/reviews, release-image provenance, deployment identity, private ingress, security, rollback, or Anchor readiness. A clean topology is not a promotion approval.

## Governed consolidation order (no automatic action)

1. **Re-verify exact identities.** Obtain a fresh authorized PR list, individual head/base refs and SHAs, `main`, `Development`, and a graph output. Record timestamp and expected hashes. If #71 moves, stop and requalify the integrated source; do not silently substitute a new source.
2. **Reconcile stack content and drift.** For every path from the three main roots to #71, examine head/parent commit ancestry and compare base-difference patches. Resolve the three stacked SHA mismatches with a human-reviewed, documented plan; preserve other contributor and unmerged stack work. Treat #22's dirty mergeability as a blocker needing conflict-resolution work in a **separate, reviewed** branch.
3. **Choose a single candidate lineage.** Identify exactly which open PRs are meant to be consolidated, which are parallel experiments, and which remain protected work. Demonstrate that no required functionality or commit disappears. Do not bulk-retarget the 36 stacked PRs, rebase them automatically, merge draft roots, force-push, close old PRs, or manufacture a duplicate main PR.
4. **Qualify a nonproduction candidate.** Freeze an immutable candidate SHA, build reproducibly, run policy, functional, regression, provenance, license/security, and environment parity checks. Hold at the Seal decision gate until the complete evidence bundle passes; Development passing local tests alone is insufficient.
5. **Request controlled promotion separately.** Only with explicit approved release authority, a verified clean/reviewed promotion diff against the latest `main`, branch-protection checks, and a complete approval trail should an authorized owner decide whether to use the existing guarded release path. No change to live or main is authorized by this report.
6. **Anchor acceptance remains independent.** Require documented production acceptance (including private ingress/health, image digest, telemetry, provider failure policy, rollback, release monitoring, and signoffs) before any Anchor claim.

### Next decision gate

**HOLD / no promotion yet.** Request a release owner to approve the *non-mutating consolidation candidate definition* (exact included parent paths and exclusions) **after** independent ancestry/patch validation and resolution of #22's dirty state. Thereafter authorize a separately scoped, nonproduction Seal candidate with required checks. Retarget/merge/main/live actions must be separately authorized and verified, not inferred from this milestone.

## Evidence integrity

This is a dated observation, not a constantly synchronized status monitor. All counts and mergeability states are transient and must be refreshed before action. The graph tool reports recorded PR API fields, not the Git server's entire commit DAG. Tests use synthetic offline PR fixtures, not a simulated successful production deployment.
The included source report and tool, if integrated into Development, do not change any PR, `main`, production service, or Anchor gate.
