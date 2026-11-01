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

## Local candidate image identity gate (unsigned, Development only)

The Foundation workflow also includes `local-image-candidate-evidence` **only
for a push to the integrated Development branch**. This isolates the expensive
Docker candidate build from draft PRs and does not publish or deploy anything.
It runs the existing clean-checkout, commit-pinned build command, then pipes
the resulting `docker image inspect` JSON into
`scripts/candidate_image_evidence.py`. The verifier independently recomputes
the source inventory and refuses any mismatch with the recorded source tree,
release-input hashes, exact commit, local image tag, OCI source/revision/version
labels, or local `sha256:` image configuration ID. A passing run retains
`search-unsigned-local-image-candidate.json` for 30 days.

This creates an auditable **local image configuration digest**, **not a
registry manifest digest**. The builder and runtime base references currently
use mutable upstream tags, so it does not establish pinned dependency closure
or reproducible build inputs. Labels are assertions made by the build, not
independently signed provenance. The job does not create an SBOM, sign an
image, retain a distributable rollback image, inspect a VPS container or
perform real provider tests. The JSON explicitly marks those unproven gates.
The image record belongs to its exact integrated Development commit; it must
not be paired with a different SHA or treated as live-deployment identity.

### Offline Dockerfile base-reference gap audit

`scripts/audit_dockerfile_base_refs.py` provides a read-only, standard-library
inventory of the *source syntax* for `FROM` instructions in the tracked
`container/builder.dockerfile` and `container/dist.dockerfile`. It verifies the
exact clean source commit and the Dockerfile hashes against the same source
baseline, rejects ambiguous Dockerfile syntax and writes only a new report:

```bash
python3 scripts/audit_dockerfile_base_refs.py \
  --expected-sha "$(git rev-parse HEAD)" \
  --output /path/to/new-base-reference-audit.json
```

At the reviewed Development source, there are **two mutable external base
tags** (`docker.io/searxng/base:searxng-builder` and
`docker.io/searxng/base:searxng`) and **one unresolved dynamic build-stage
reference** (`${BUILDER_IMAGE}`). The audit reports their source file, line,
literal reference and classification. A digest-form `FROM` would establish
only digest **syntax**, not whether that digest was resolved, inspected,
signed, vulnerable, or included in a complete SBOM. The dynamic builder-stage
reference is later supplied by a source-scoped local image tag in the build
script; its actual image configuration digest is outside this offline audit.
Every report deliberately returns `HOLD_NO_SEAL_OR_ANCHOR_QUALIFICATION`,
even if all literal external references eventually use digests.

The Foundation workflow's `exact-source-baseline` job is configured to run
this audit at its exact checked-out source SHA on both PR and push events and
retain `search-dockerfile-base-reference-hold` for 30 days. This configuration
is source-reviewed; an actual head-specific successful CI execution must be
read back before claiming the artifact was produced for any candidate.

This diagnostic neither edits Dockerfiles nor pulls images, pins upstream
tags, generates a complete SBOM, evaluates vulnerabilities, signs artifacts,
or verifies a released/deployed image. A future controlled build must resolve
and record immutable build-stage/base images, complete dependency and license
evidence, signature/attestation and approved distribution/rollback provenance
before the corresponding Seal gates can close.

### Partial installed-Python dependency observation

The same gated Development image job now performs a **no-network, read-only
ephemeral Docker run by its exact local image configuration digest**, with
capabilities removed, no-new-privileges, bounded CPU/memory/processes and only
a read-only mount of the inventory program. The program uses Python's standard
`importlib.metadata` to list installed distribution **names and versions**,
without installing, importing application modules, querying providers or
reading credentials. The offline verifier matches this data to the same exact
source inventory, OCI candidate identity, digest and Linux architecture,
rejects duplicate/ambiguous package names and malformed values, and retains
`search-local-python-distributions.json` for 30 days if all checks pass.

This Python inventory is **not a complete SBOM**: it excludes OS packages,
shared libraries, non-Python artifacts, dependency relationships, licenses, vulnerability
assessments and origin/signature proof; packages can be unpinned upstream.
It cannot prove exactly what image runs on the VPS, which base images were
resolved, that a container image is reproducible, or that the package list is
trustworthy beyond the isolated CI observation. The artifact is explicitly
unsigned and must not be used as Seal/Anchor qualification. A verified,
complete SPDX/CycloneDX SBOM and required signatures remain a separate gate.

### Runtime OS identity and package-registry availability (unsigned; no OS SBOM)

The Development-only candidate job additionally performs a separate isolated
observation against the **same exact local image ID**, without network,
filesystem writes, privileges or access to secrets. The source-pinned Python
reader recognizes two distinct cases:

- Alpine APK / Debian dpkg images with **one present, supported, parseable**
  registration database: extract sorted, validated installed package
  name/version/architecture rows as explicitly partial package evidence.
- The currently used SearXNG base image is **Void Linux**, a rolling-release OS
  whose `os-release` legitimately omits `VERSION_ID`. The upstream `searxng`
  runtime Dockerfile intentionally removes XBPS and `/var/db/` after assembling
  the root filesystem. Only when `ID=void`, `VERSION_ID` is absent, no APK/dpkg
  database exists and no `/var/db/xbps*` entry exists does the reader classify
  `package_inventory_status: unavailable`. The output includes OS identity,
  expected XBPS manager and explicit registry-removal reason, but **no OS
  package list, zero count, manifest hash or inferred package identities**.

Both variants are independently bound to the exact clean source manifest,
local image configuration digest, Linux architecture and previously verified
Python evidence. Unexpected OS/manager combinations, malformed records,
retained XBPS registry, new/unrecognized distro states or changed image/source
evidence fail closed. A successful observation retains
`search-local-os-observation.json` for 30 days. No `xbps`, `apk`, `dpkg`,
`apt` or network command runs in the image. The upstream base implementation
is documented at https://github.com/searxng/base/blob/main/Dockerfile.

**The Void unavailable branch is a verified evidence gap, not an OS package
inventory success or an Anchor qualification.** There is no evidence about
which OS packages, bundled executables or shared libraries are present or
their versions. Even when another distro's package database is readable,
manager records omit manually copied binaries, transitive dependency edges,
licenses, vulnerabilities, signatures and full content hashes. Upstream base
tags remain mutable. A green source or CI workflow means only that the
strictly limited observation was recorded; **complete OS package/BOM
qualification remains blocked** until trusted pre-stripping build-stage or
independently verified static image analysis becomes available. No Seal/Anchor,
deployed-image, security or OS-hardening qualification follows.

### Bounded selected ELF-file hash observation (unsigned; still no OS package inventory)

For the exact same isolated Development-only image, a further read-only and
unprivileged, network-disabled run hashes **regular ELF-magic files** in a
strictly scoped path selection: recognized core executable filenames directly
under `/usr/bin` (including `/usr/bin/busybox`) and regular shared-library
filenames directly under `/usr/lib`. The Python standard-library scanner only
reads candidate files, hashes them in chunks and emits sorted absolute path,
byte size and SHA-256 records. It does not execute discovered binaries, query
package managers, inspect credentials or traverse arbitrary directories.
Symlinks and non-ELF files are excluded; root/system-directory symlinks are
rejected. Directory entries, selected files, per-file size and total bytes are
strictly bounded; unreadable, changed or unexpectedly structured input fails
closed. This selection is intentionally **not** an exhaustive runtime ELF
inventory or a transitive shared-library dependency graph.

`scripts/verify_runtime_binary_hash_inventory.py` independently reruns the
exact-source/image/Python/Void registry-gap checks, then validates sorted
unique allowlisted paths, file sizes, SHA-256 values and aggregate count. Its
result includes the full selected hash rows, an independent selected-manifest
hash, the exact image configuration digest/source tree/commit/architecture,
and a SHA-256 of the previously accepted OS-gap evidence. It can only succeed
when that evidence says the Void XBPS registry was removed and **installed OS
package identities and versions remain unavailable**. Passing integrated
Development runs retain the separate
`search-local-selected-elf-hashes.json` artifact for 30 days; all outputs are
explicitly unsigned.

File hashes may help compare two known local image candidates or detect a
later content change at those selected paths. They **do not identify owning
packages or versions**, prove upstream provenance, include symlink targets,
include every executable/library, or establish complete SPDX/CycloneDX SBOM,
vulnerability/license clearance, image signature, immutable base-image
dependencies, reproducibility, deployment identity or Seal/Anchor acceptance.
Until the integrated Development image job actually executes this additional
step, these are implementation and test properties, **not observed runtime
results**. The Void OS-package and full dependency-closure blockers remain.

The initial integrated Docker build exposed a runner parser failure on the
upstream builder's `COPY --exclude` instruction. The builder now uses a
Dockerfile-specific context ignore file to exclude generated
`searx/version_frozen.py`; the distribution image retains its existing root
context rules so that the pinned build helper can copy the freshly generated
version file. Both ignore files are enumerated in the source inventory. This
is a build-compatibility correction, not an acceptance of the first failed
image candidate; the full image build must pass on the corrected source.
The same builder also used an invalid GNU `find -exec` argument form for
verifying compressed files (`{}.gz` / `{}.br` with the batching `+` form).
The corrected builder discovers already-created `.gz` and `.br` files and
tests them with standalone `{}` arguments; this is covered by offline
regressions but still requires a real Docker build to be accepted.

**Acceptance sequence:** observe a green exact-head post-merge run and retain
the JSON; independently fix/pin dependencies and generate signed provenance
plus SBOM where required; create a controlled release line and rollback
artifact; then compare an approved deployed image digest to the release
artifact through private-ingress/security and restore drills. There is no
promotion from these source/CI checks alone.

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
