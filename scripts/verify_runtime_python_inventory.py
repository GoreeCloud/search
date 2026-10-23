#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bind a no-network local image's Python packages to exact source identity.

The inventory is a partial, unsigned dependency observation, not a complete
SPDX/CycloneDX SBOM, package vulnerability evaluation, pinned build proof,
image signature or deployed-image identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from runtime_python_inventory import MAX_DISTRIBUTIONS, NAME, VERSION, normalize_name
from source_baseline_inventory import BaselineError, REPO, REPO_URL, collect


SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
PYTHON_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
MAX_JSON_BYTES = 512 * 1024


class DependencyEvidenceError(Exception):
    """Installed dependency evidence cannot be bound to a trusted image."""


def verify(runtime: dict, image: dict, current_source: dict, sha: str, image_id: str) -> dict:
    if not isinstance(image_id, str) or not SHA256.fullmatch(image_id):
        raise DependencyEvidenceError("local image configuration ID is malformed")
    if not isinstance(image, dict) or not isinstance(current_source, dict):
        raise DependencyEvidenceError("source or image record is malformed")
    if (
        image.get("schema") != "goreecloud.search.local-image-candidate.v1"
        or image.get("source_commit") != sha
        or image.get("repository") != REPO_URL
        or image.get("source_tree") != current_source.get("source_tree")
        or image.get("release_input_sha256") != current_source.get("input_sha256")
        or image.get("local_image_config_digest") != image_id
        or image.get("image_tag") != f"goreecloud/search:staging-{sha[:12]}"
        or image.get("unsigned") is not True
    ):
        raise DependencyEvidenceError("image identity does not match exact clean source")
    if (
        not isinstance(runtime, dict)
        or set(runtime) != {"schema", "python_version", "implementation", "os", "machine", "distributions"}
        or runtime.get("schema") != "goreecloud.search.runtime-python-distributions.v1"
    ):
        raise DependencyEvidenceError("unexpected installed distribution record schema")
    platform_id = image.get("platform")
    arch = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}.get(platform_id)
    if runtime.get("os") != "linux" or runtime.get("machine") != arch or arch is None:
        raise DependencyEvidenceError("observed Python runtime platform differs from candidate")
    if runtime.get("implementation") != "CPython" or not isinstance(runtime.get("python_version"), str) or not PYTHON_VERSION.fullmatch(runtime["python_version"]):
        raise DependencyEvidenceError("Python runtime identity is malformed")
    distributions = runtime.get("distributions")
    if not isinstance(distributions, list) or not 0 < len(distributions) <= MAX_DISTRIBUTIONS:
        raise DependencyEvidenceError("Python distribution count is invalid")
    names = []
    for package in distributions:
        if not isinstance(package, dict) or set(package) != {"name", "version"}:
            raise DependencyEvidenceError("unexpected Python distribution field")
        name, version = package["name"], package["version"]
        if not isinstance(name, str) or not NAME.fullmatch(name) or normalize_name(name) != name:
            raise DependencyEvidenceError("distribution names must be normalized")
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise DependencyEvidenceError("invalid Python distribution version")
        names.append(name)
    if names != sorted(set(names)):
        raise DependencyEvidenceError("Python distributions are not sorted and unique")
    serialized = json.dumps(distributions, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema": "goreecloud.search.local-python-dependency-evidence.v1",
        "repository": REPO_URL,
        "source_commit": sha,
        "source_tree": current_source["source_tree"],
        "local_image_config_digest": image_id,
        "image_tag": image["image_tag"],
        "platform": platform_id,
        "python_version": runtime["python_version"],
        "distribution_count": len(distributions),
        "distribution_manifest_sha256": hashlib.sha256(serialized).hexdigest(),
        "distributions": distributions,
        "unsigned": True,
        "evidence_scope": "isolated_local_image_installed_python_distribution_names_and_versions_only",
        "not_evaluated": [
            "non_python_os_or_binary_dependencies",
            "complete_sbom_licenses_and_vulnerabilities",
            "pinned_base_images_or_reproducible_build",
            "cryptographic_attestation_or_signature",
            "registry_manifest_digest_or_rollback_artifact",
            "deployed_image_and_runtime_acceptance",
            "seal_and_anchor_qualification",
        ],
    }


def load(raw: bytes) -> object:
    if len(raw) > MAX_JSON_BYTES:
        raise DependencyEvidenceError("JSON evidence exceeds size limit")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DependencyEvidenceError("JSON evidence is malformed") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--local-image-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        current_source = collect(REPO, args.expected_sha)
        image = load(args.local_image_evidence.read_bytes())
        runtime = load(sys.stdin.buffer.read(MAX_JSON_BYTES + 1))
        evidence = verify(runtime, image, current_source, args.expected_sha, args.image_id)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (DependencyEvidenceError, BaselineError, OSError, ValueError, TypeError) as error:
        message = str(error) if isinstance(error, (DependencyEvidenceError, BaselineError)) else "dependency evidence could not be safely read or written"
        parser.exit(2, f"LOCAL_PYTHON_DEPENDENCY_BLOCKED: {message}\n")
    print("LOCAL_PYTHON_DEPENDENCY_PASS: unsigned partial package inventory; no SBOM/signature/release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
