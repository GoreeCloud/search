#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Record an unsigned local Docker image identity against exact Search source.

Reads the JSON output of `docker image inspect` from standard input. The
result is local candidate evidence only: OCI labels are self-declared, and a
local image configuration digest is not a registry manifest digest, signature,
SBOM, reproducible-build proof or deployment acceptance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from source_baseline_inventory import BaselineError, REPO, REPO_URL, collect


SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
MAX_JSON_BYTES = 2 * 1024 * 1024
SCHEMA = "goreecloud.search.local-image-candidate.v1"


class ImageEvidenceError(Exception):
    """The local candidate image cannot be matched to verified source."""


def verify(baseline: dict, actual_source: dict, inspection: object, sha: str) -> dict:
    """Require exact source evidence and one correctly labeled local image."""
    if baseline != actual_source or baseline.get("source_commit") != sha:
        raise ImageEvidenceError("source inventory does not match the clean checkout")
    if not isinstance(inspection, list) or len(inspection) != 1:
        raise ImageEvidenceError("expected exactly one Docker image inspect record")
    record = inspection[0]
    if not isinstance(record, dict):
        raise ImageEvidenceError("invalid Docker image inspect record")
    image_id = record.get("Id")
    if not isinstance(image_id, str) or not SHA256.fullmatch(image_id):
        raise ImageEvidenceError("missing or invalid local image configuration digest")
    image_tag = f"goreecloud/search:staging-{sha[:12]}"
    repo_tags = record.get("RepoTags")
    if not isinstance(repo_tags, list) or image_tag not in repo_tags:
        raise ImageEvidenceError("the inspected image is not the expected candidate tag")
    config = record.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if not isinstance(labels, dict):
        raise ImageEvidenceError("candidate image has no OCI identity labels")
    expected = {
        "org.opencontainers.image.revision": sha,
        "org.opencontainers.image.source": REPO_URL,
        "org.opencontainers.image.version": f"dev-{sha[:12]}",
    }
    if any(labels.get(label) != value for label, value in expected.items()):
        raise ImageEvidenceError("candidate image OCI identity differs from source")
    if record.get("Os") != "linux" or record.get("Architecture") not in ("amd64", "arm64"):
        raise ImageEvidenceError("unexpected local candidate platform")

    return {
        "schema": SCHEMA,
        "repository": REPO_URL,
        "source_commit": sha,
        "source_tree": baseline["source_tree"],
        "release_input_sha256": baseline["input_sha256"],
        "image_tag": image_tag,
        "local_image_config_digest": image_id,
        "platform": f"linux/{record['Architecture']}",
        "evidence_scope": "clean_source_and_local_docker_image_inspect",
        "unsigned": True,
        "not_evaluated": [
            "registry_manifest_digest_or_distribution",
            "pinned_base_images_and_reproducible_build",
            "sbom_dependency_or_vulnerability_attestation",
            "cryptographic_build_attestation_or_signature",
            "deployed_image_identity_and_rollback_artifact",
            "runtime_provider_security_privacy_and_platform_acceptance",
            "seal_and_anchor_qualification",
        ],
    }


def _load_json(raw: bytes) -> object:
    if len(raw) > MAX_JSON_BYTES:
        raise ImageEvidenceError("JSON evidence exceeds size limit")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ImageEvidenceError("JSON evidence is malformed") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--source-baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        # Recompute from the checkout rather than trusting a caller's JSON.
        actual = collect(REPO, args.expected_sha)
        baseline = _load_json(args.source_baseline.read_bytes())
        inspected = _load_json(sys.stdin.buffer.read(MAX_JSON_BYTES + 1))
        if not isinstance(baseline, dict):
            raise ImageEvidenceError("source inventory is not an object")
        evidence = verify(baseline, actual, inspected, args.expected_sha)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (BaselineError, ImageEvidenceError, FileExistsError, OSError, ValueError, TypeError) as error:
        # Don't print remote output, environment secrets, or unknown file paths.
        if isinstance(error, (BaselineError, ImageEvidenceError)):
            reason = str(error)
        else:
            reason = "candidate evidence could not be safely read or written"
        parser.exit(2, f"IMAGE_IDENTITY_BLOCKED: {reason}\n")
    print("LOCAL_IMAGE_IDENTITY_PASS: unsigned candidate record created; no image published or deployed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
