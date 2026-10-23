#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Inventory exact-source Dockerfile FROM references without resolving images.

An immutable-looking digest in source is not proof that an image was pulled,
signed, scanned or deployed. This is a deliberately nonpromoting evidence gap
report, not a Dockerfile interpreter or a Seal/Anchor acceptance decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from source_baseline_inventory import BaselineError, REPO, REPO_URL, collect


DOCKERFILES = ("container/builder.dockerfile", "container/dist.dockerfile")
MAX_FILE_BYTES = 128 * 1024
MAX_STAGES = 32
REFERENCE = re.compile(r"[A-Za-z0-9_./:@${}-]{1,256}\Z")
DIGEST = re.compile(r"[A-Za-z0-9_./:-]+@sha256:[0-9a-f]{64}\Z")
FROM = re.compile(r"^FROM\s+(.+)$", re.IGNORECASE)


class BaseReferenceError(Exception):
    """A source or Dockerfile instruction cannot be safely classified."""


def scan(name: str, raw: bytes) -> list[dict]:
    """Classify literal, variable, and local-stage references conservatively."""
    if len(raw) > MAX_FILE_BYTES or not raw:
        raise BaseReferenceError("Dockerfile is empty or exceeds its byte budget")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        raise BaseReferenceError("Dockerfile is not UTF-8") from None
    if any(len(line) > 8192 for line in lines):
        raise BaseReferenceError("Dockerfile contains an excessive line")
    stages: set[str] = set()
    records = []
    for number, line in enumerate(lines, 1):
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        match = FROM.fullmatch(clean)
        if not match:
            continue
        tokens = match.group(1).split()
        # Docker allows an optional --platform=X before the image token.
        if tokens and tokens[0].startswith("--platform="):
            if tokens[0] == "--platform=":
                raise BaseReferenceError("empty FROM platform")
            tokens.pop(0)
        if len(tokens) not in (1, 3) or (len(tokens) == 3 and tokens[1].lower() != "as"):
            raise BaseReferenceError("unsupported or continued Dockerfile FROM instruction")
        ref = tokens[0]
        alias = tokens[2].lower() if len(tokens) == 3 else None
        if not REFERENCE.fullmatch(ref) or (alias and not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", alias)):
            raise BaseReferenceError("invalid or ambiguous Dockerfile reference")
        if alias and alias in stages:
            raise BaseReferenceError("Dockerfile stage name is duplicated")
        if ref.lower() == "scratch":
            classification = "empty_scratch_base"
        elif ref.lower() in stages:
            classification = "prior_local_stage"
        elif "$" in ref:
            classification = "unresolved_build_argument"
        elif DIGEST.fullmatch(ref):
            classification = "digest_syntax_only_unverified"
        else:
            # A malformed @sha256 form is not merely a harmless mutable tag.
            if "@" in ref:
                raise BaseReferenceError("malformed base image digest")
            classification = "mutable_or_unpinned_external_reference"
        records.append({"dockerfile": name, "line": number,
                        "reference": ref, "classification": classification})
        if alias:
            stages.add(alias)
        if len(records) > MAX_STAGES:
            raise BaseReferenceError("Dockerfile has too many build stages")
    if not records:
        raise BaseReferenceError("Dockerfile has no classifiable FROM instructions")
    return records


def audit(source: dict, dockerfiles: dict[str, bytes]) -> dict:
    """Bind classifications to already checked, exact-source input hashes."""
    if (not isinstance(source, dict)
            or source.get("schema") != "goreecloud.search.source-baseline.v1"
            or source.get("repository") != REPO_URL
            or not isinstance(source.get("input_sha256"), dict)
            or set(dockerfiles) != set(DOCKERFILES)):
        raise BaseReferenceError("source or Dockerfile inventory is incomplete")
    rows = []
    for path in DOCKERFILES:
        raw = dockerfiles[path]
        if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != source["input_sha256"].get(path):
            raise BaseReferenceError("Dockerfile content differs from exact source inventory")
        rows.extend(scan(path, raw))
    blockers = [r for r in rows if r["classification"] in (
        "mutable_or_unpinned_external_reference", "unresolved_build_argument")]
    return {
        "schema": "goreecloud.search.dockerfile-base-reference-audit.v1",
        "repository": REPO_URL,
        "source_commit": source["source_commit"],
        "source_tree": source["source_tree"],
        "from_references": rows,
        "unresolved_or_mutable_reference_count": len(blockers),
        "release_decision": "HOLD_NO_SEAL_OR_ANCHOR_QUALIFICATION",
        "blocking_reasons": (["mutable or dynamic Dockerfile FROM references have no immutable image closure"]
                             if blockers else ["digest syntax alone has no verified image resolution or provenance"]),
        "not_evaluated": [
            "actual_build_arg_values_or_resolved_base_image_ids",
            "registry_manifest_digest_and_platform_specific_layers",
            "upstream_image_licenses_vulnerabilities_or_complete_sbom",
            "cryptographic_attestation_or_signature",
            "native_platform_builds_deployment_recovery_or_runtime_acceptance",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, help="new JSON path; existing files are not overwritten")
    args = parser.parse_args(argv)
    try:
        source = collect(REPO, args.expected_sha)
        report = audit(source, {path: (REPO / path).read_bytes() for path in DOCKERFILES})
        output = json.dumps(report, sort_keys=True, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(output)
        else:
            print(output, end="")
    except (BaseReferenceError, BaselineError, OSError, ValueError, TypeError):
        parser.exit(2, "BASE_REFERENCE_AUDIT_BLOCKED: exact source or Dockerfile audit unavailable\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
