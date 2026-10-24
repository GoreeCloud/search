#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bind OS registry observation to an exact verified local image and Python evidence.

For Void images with their XBPS registry deliberately removed, this records
an explicit unavailable status and NO package inventory. Neither branch can
certify an SBOM, binary closure, signing, Seal or Anchor qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from runtime_os_inventory import (
    InventoryError, MAX_PACKAGES, PACKAGE_ARCH, PACKAGE_NAME, PACKAGE_VERSION,
    RELEASE_FIELD, RELEASE_VERSION,
)
from source_baseline_inventory import BaselineError, REPO, REPO_URL, collect
from verify_runtime_python_inventory import SHA256
from runtime_python_inventory import MAX_DISTRIBUTIONS, NAME, VERSION, normalize_name


MAX_JSON_BYTES = 2 * 1024 * 1024


class OSPackageEvidenceError(Exception):
    """Runtime OS evidence cannot be bound to the exact source/image."""


def verify(runtime: dict, image: dict, python: dict, source: dict, sha: str, image_id: str) -> dict:
    if not isinstance(image_id, str) or not SHA256.fullmatch(image_id):
        raise OSPackageEvidenceError("local image ID is malformed")
    if not all(isinstance(x, dict) for x in (runtime, image, python, source)):
        raise OSPackageEvidenceError("OS, Python, source or image evidence is malformed")
    if (
        image.get("schema") != "goreecloud.search.local-image-candidate.v1"
        or image.get("repository") != REPO_URL
        or image.get("source_commit") != sha
        or image.get("source_tree") != source.get("source_tree")
        or image.get("release_input_sha256") != source.get("input_sha256")
        or image.get("local_image_config_digest") != image_id
        or image.get("image_tag") != f"goreecloud/search:staging-{sha[:12]}"
        or image.get("unsigned") is not True
    ):
        raise OSPackageEvidenceError("local candidate image differs from exact clean source")
    platform_id = image.get("platform")
    machine = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}.get(platform_id)
    if machine is None:
        raise OSPackageEvidenceError("unsupported local image platform")
    if (
        python.get("schema") != "goreecloud.search.local-python-dependency-evidence.v1"
        or python.get("source_commit") != sha
        or python.get("source_tree") != source.get("source_tree")
        or python.get("local_image_config_digest") != image_id
        or python.get("image_tag") != image.get("image_tag")
        or python.get("platform") != platform_id
        or python.get("unsigned") is not True
        or not isinstance(python.get("distribution_count"), int)
        or python["distribution_count"] <= 0
        or not isinstance(python.get("distribution_manifest_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", python["distribution_manifest_sha256"])
    ):
        raise OSPackageEvidenceError("Python distribution evidence belongs to another candidate")
    python_packages = python.get("distributions")
    if (not isinstance(python_packages, list) or not 0 < len(python_packages) <= MAX_DISTRIBUTIONS
            or python["distribution_count"] != len(python_packages)):
        raise OSPackageEvidenceError("previous Python evidence has an invalid distribution count")
    python_names = []
    for package in python_packages:
        if not isinstance(package, dict) or set(package) != {"name", "version"}:
            raise OSPackageEvidenceError("previous Python evidence has unexpected package fields")
        name, version = package["name"], package["version"]
        if (not isinstance(name, str) or not NAME.fullmatch(name)
                or normalize_name(name) != name or not isinstance(version, str)
                or not VERSION.fullmatch(version)):
            raise OSPackageEvidenceError("previous Python evidence has invalid package identity")
        python_names.append(name)
    if python_names != sorted(set(python_names)):
        raise OSPackageEvidenceError("previous Python evidence has duplicate or unsorted packages")
    python_distribution_bytes = json.dumps(
        python_packages, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if hashlib.sha256(python_distribution_bytes).hexdigest() != python["distribution_manifest_sha256"]:
        raise OSPackageEvidenceError("previous Python evidence manifest hash is inconsistent")
    if runtime.get("os") != "linux" or runtime.get("machine") != machine:
        raise OSPackageEvidenceError("OS runtime schema or platform mismatches the candidate")
    release = runtime.get("release")
    if runtime.get("schema") == "goreecloud.search.runtime-os-registry-unavailable.v1":
        if (
            set(runtime) != {"schema", "os", "machine", "release", "package_manager",
                             "package_inventory_status", "reason"}
            or release != {"id": "void", "version_id": None}
            or runtime.get("package_manager") != "xbps"
            or runtime.get("package_inventory_status") != "unavailable"
            or runtime.get("reason") != "runtime_xbps_package_registry_removed"
        ):
            raise OSPackageEvidenceError("unknown or contradictory unavailable OS registry state")
        python_bytes = json.dumps(python, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {
            "schema": "goreecloud.search.local-os-registry-unavailable-evidence.v1",
            "repository": REPO_URL,
            "source_commit": sha,
            "source_tree": source["source_tree"],
            "local_image_config_digest": image_id,
            "image_tag": image["image_tag"],
            "platform": platform_id,
            "os_release": release,
            "package_manager": "xbps",
            "package_inventory_status": "unavailable",
            "reason": "runtime_xbps_package_registry_removed",
            "python_evidence_sha256": hashlib.sha256(python_bytes).hexdigest(),
            "unsigned": True,
            "evidence_scope": "isolated_local_image_os_identity_and_registry_absence_only",
            "not_evaluated": [
                "installed_os_packages_and_binary_dependencies",
                "complete_spdx_cyclonedx_sbom_dependencies_licenses_or_vulnerabilities",
                "pinned_base_images_or_reproducible_build",
                "cryptographic_attestation_or_signature",
                "registry_manifest_digest_or_rollback_artifact",
                "deployed_image_and_runtime_acceptance",
                "seal_and_anchor_qualification",
            ],
        }
    if (set(runtime) != {"schema", "os", "machine", "release", "package_manager", "packages"}
            or runtime.get("schema") != "goreecloud.search.runtime-os-packages.v1"):
        raise OSPackageEvidenceError("unsupported OS inventory schema")
    if (not isinstance(release, dict) or set(release) != {"id", "version_id"}
            or not isinstance(release.get("id"), str)
            or not RELEASE_FIELD.fullmatch(release["id"])
            or not isinstance(release.get("version_id"), str)
            or not RELEASE_VERSION.fullmatch(release["version_id"])):
        raise OSPackageEvidenceError("OS release identity is malformed")
    manager = runtime.get("package_manager")
    if manager not in ("dpkg", "apk"):
        raise OSPackageEvidenceError("unsupported package-manager evidence")
    if (release["id"], manager) not in {("alpine", "apk"), ("debian", "dpkg"),
                                             ("ubuntu", "dpkg")}:
        raise OSPackageEvidenceError("OS release does not match the package manager")
    allowed_arch = {
        ("dpkg", "linux/amd64"): {"amd64", "all"},
        ("dpkg", "linux/arm64"): {"arm64", "all"},
        ("apk", "linux/amd64"): {"x86_64", "noarch"},
        ("apk", "linux/arm64"): {"aarch64", "noarch"},
    }[(manager, platform_id)]
    packages = runtime.get("packages")
    if not isinstance(packages, list) or not 0 < len(packages) <= MAX_PACKAGES:
        raise OSPackageEvidenceError("installed OS package count is invalid")
    keys: list[tuple[str, str]] = []
    for package in packages:
        if not isinstance(package, dict) or set(package) != {"name", "version", "arch"}:
            raise OSPackageEvidenceError("unexpected OS package entry fields")
        name, version, arch = package["name"], package["version"], package["arch"]
        if (not isinstance(name, str) or not PACKAGE_NAME.fullmatch(name)
                or not isinstance(version, str) or not PACKAGE_VERSION.fullmatch(version)
                or not isinstance(arch, str) or not PACKAGE_ARCH.fullmatch(arch)
                or arch not in allowed_arch):
            raise OSPackageEvidenceError("OS package name/version/architecture is invalid")
        keys.append((name, arch))
    if keys != sorted(set(keys)):
        raise OSPackageEvidenceError("OS package records are not sorted and unique")
    serialized = json.dumps(packages, sort_keys=True, separators=(",", ":")).encode("utf-8")
    python_bytes = json.dumps(python, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema": "goreecloud.search.local-os-package-evidence.v1",
        "repository": REPO_URL,
        "source_commit": sha,
        "source_tree": source["source_tree"],
        "local_image_config_digest": image_id,
        "image_tag": image["image_tag"],
        "platform": platform_id,
        "os_release": release,
        "package_manager": manager,
        "package_count": len(packages),
        "package_manifest_sha256": hashlib.sha256(serialized).hexdigest(),
        "python_evidence_sha256": hashlib.sha256(python_bytes).hexdigest(),
        "packages": packages,
        "unsigned": True,
        "evidence_scope": "isolated_local_image_package_manager_registered_packages_only",
        "not_evaluated": [
            "manually_copied_or_unregistered_executables_and_shared_libraries",
            "complete_spdx_cyclonedx_sbom_dependencies_licenses_or_vulnerabilities",
            "pinned_base_images_or_reproducible_build",
            "cryptographic_attestation_or_signature",
            "registry_manifest_digest_or_rollback_artifact",
            "deployed_image_and_runtime_acceptance",
            "seal_and_anchor_qualification",
        ],
    }


def load(raw: bytes) -> object:
    if len(raw) > MAX_JSON_BYTES:
        raise OSPackageEvidenceError("OS evidence JSON exceeds the size budget")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OSPackageEvidenceError("OS evidence JSON is malformed") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--local-image-evidence", type=Path, required=True)
    parser.add_argument("--python-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = collect(REPO, args.expected_sha)
        image = load(args.local_image_evidence.read_bytes())
        python = load(args.python_evidence.read_bytes())
        runtime = load(sys.stdin.buffer.read(MAX_JSON_BYTES + 1))
        record = verify(runtime, image, python, source, args.expected_sha, args.image_id)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True, indent=2)
            stream.write("\n")
    except (OSPackageEvidenceError, InventoryError, BaselineError, OSError, ValueError, TypeError):
        parser.exit(2, "LOCAL_OS_PACKAGE_EVIDENCE_BLOCKED: could not verify exact OS package evidence\n")
    if record["schema"] == "goreecloud.search.local-os-registry-unavailable-evidence.v1":
        print("LOCAL_OS_REGISTRY_UNAVAILABLE_VERIFIED: no OS package inventory; Anchor remains blocked")
    else:
        print("LOCAL_OS_PACKAGE_EVIDENCE_PASS: unsigned registered packages only; no complete SBOM or release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
