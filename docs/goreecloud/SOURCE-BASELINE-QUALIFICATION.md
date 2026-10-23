# GoreeCloud Search — exact source baseline and release qualification

**Checkpoint: October 23, 2026.** Scope: Development source and release-input
provenance only. This record does **not** declare a frozen Seal candidate, an
Anchor release, a new deployment, or accepted native/platform behavior.

## Observed source and deployment boundaries

| Boundary | Verified or recorded identity | Meaning |
| --- | --- | --- |
| Authorized source repository | `GoreeCloud/search` | GitHub is the authority for branches, PRs and checks |
| `main` at checkpoint | `278fdb45c5688472aa7c547c5b3906c194c2e2b9` | README-only landing baseline, not deployed application source |
| Integrated Development base, before this work | `87aceb2ffbfc078ba09ba2e01f57978ec4e71638` | Source head after PR #86; four post-merge foundation/native workflows passed |
| Release-source consolidation | [Draft PR #71](https://github.com/GoreeCloud/search/pull/71), with stacked predecessors | Not merged into `main`; resolve the stack without overwriting reviewed work |
| Last documented live NetBird Development image source | `40caeb47a1fd8fc15a60f54e5e383d1a9f280598` | [October 20 verified cutover](../../deploy/vps/FREE-WORKING-SOURCES-CUTOVER.md); not rechecked live by this inventory |

The source, GitHub Actions checkout, built image, signed artifact, current
running image and production release are different evidence boundaries.
A source hash or declared OCI revision label is **not** a build signature or
proof of which image is serving traffic.

## Reproducible, source-only inventory

The offline standard-library tool
`scripts/source_baseline_inventory.py` requires:

1. A full, caller-supplied 40-character source commit matching checkout HEAD.
2. An exact authorized `GoreeCloud/search` origin (not another GitHub identity).
3. A clean Git checkout with an exact Git tree identifier.
4. Every enumerated build, deployment-profile, requirements and CI input
   committed as a regular file; their SHA-256 hashes are captured.

From a **clean** checkout:

```bash
python3 scripts/source_baseline_inventory.py \
  --expected-sha "$(git rev-parse HEAD)"
```

The output contains no search queries, provider URLs, secrets, environment
variables, working-tree filenames or live runtime data. On ambiguity it
fails closed; it does not suggest that a check failed for a specific sensitive
untracked file.

The Foundation workflow now performs a separate
`exact-source-baseline` job for pushes and PRs. On pull requests it checks
out the **actual PR head SHA**, not GitHub's synthetic merge SHA, and saves
`search-source-baseline.json` as a 30-day workflow artifact. The other
Foundation jobs continue testing the checked-out merge integration state.
This distinction must be retained when mapping a reviewed head to CI.
The inventory is designed to be reproduced from the exact later candidate;
this document's dated source references do not replace a fresh manifest.

The inventory's explicit `not_evaluated` list covers artifact identity,
cryptographic provenance, provider/runtime acceptance, native platforms,
GC UI, nine-system integration, security and privacy, recovery,
production acceptance, and Seal/Anchor qualification. It must not be
interpreted as a positive acceptance verdict for any of them.

## Candidate convergence and Anchor blockers

| Gate | Current decision and necessary evidence |
| --- | --- |
| Single release baseline | **Open.** Reconcile the draft stacked source PRs, select an exact controlled release line, and establish branch protection/review/check requirements applicable to that line |
| Build-to-deploy provenance | **Open.** Produce and verify a candidate image digest, pinned inputs, SBOM/dependency safety, attestation/signature where required, configuration identity and retained rollback artifact; compare to running image |
| Product and provider | **Open.** Complete Web/Images/Videos/News behavior, sustained legitimate provider reliability, rate/failure handling and no silent engine substitution; never work around blocks or CAPTCHAs |
| Privacy, security and access | **Open.** Qualify actual direct-HTTPS provider disclosure, internal/metadata/DNS/IPv6 egress denial, request budgets, identity/authorization, logs and production-private ingress |
| Native and GC UI | **Open.** The existing web SearXNG-derived interface is not GC UI-accepted; native GoreeCloud-owned application/service architecture and actual supported OS builds need their own acceptance |
| Integral systems | **Open.** Assess all nine system contracts, implement applicable consumers and record justifiable non-applicability with current integration evidence |
| Recovery and operations | **Open.** Exercise clean installation, updates, backup/restore, exact rollback, monitoring/alerting and representative-device/runtime checks |
| Seal and Anchor | **Blocked.** First close known candidate-blocking development, freeze and qualify an exact Seal candidate, then complete all applicable Anchor/production acceptance and stabilization requirements |

The canonical current UI authority is **GoreeCloud UI (GC UI)**, not the
retired design-system terminology retained in older lifecycle standards.
The source fork is **not** evidence of compliance with the native
GoreeCloud-owned application requirement. Historical healthy containers,
green tests or a NetBird HTTP 200 are Development observations, not an
Anchor decision.

**Operational tracking:** [Linear GOR-25](https://linear.app/goreecloud/issue/GOR-25/reconcile-and-complete-goreecloud-search-nativeplatform-modernization),
[source/deployment provenance issue #33](https://github.com/GoreeCloud/search/issues/33),
[provider reliability issue #26](https://github.com/GoreeCloud/search/issues/26),
and [egress security issue #21](https://github.com/GoreeCloud/search/issues/21).
The corresponding Todoist qualification task remains active. Do not change
production, public routing, DNS, NetBird, containers, or release labels on
the strength of this source inventory alone.
