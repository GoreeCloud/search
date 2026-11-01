#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bind selected runtime ELF-file hashes to exact unsigned Development evidence.

The fixed path selection is deliberately incomplete, and the Void XBPS
package database remains unavailable. No package, SBOM, signature, vulnerability,
deployment, Seal or Anchor claim may be inferred from this observation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from runtime_binary_hash_inventory import (
    DIRECTORIES, FILE_NAME, MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES,
)
from source_baseline_inventory import BaselineError, REPO, REPO_URL, collect
from verify_runtime_os_inventory import (
    OSPackageEvidenceError, load as load_bounded_json,
    verify as verify_previous_os_chain,
)
from verify_runtime_python_inventory import SHA256


MAX_JSON_BYTES = 2 * 1024 * 1024
SELECTION = "regular_elf_magic_usr_bin_tools_and_direct_usr_lib_shared_libraries_v1"
PATH_MATCHERS = tuple(("/" + relative + "/", matcher) for relative, matcher in DIRECTORIES)
HEX_HASH = re.compile(r"[0-9a-f]{64}\Z")


class BinaryEvidenceError(Exception):
    """Selected runtime binary evidence is malformed or incompletely bound."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify(runtime: dict, image: dict, python: dict, os_evidence: dict,
           source: dict, sha: str, image_id: str) -> dict:
    """Verify a fixed partial file-hash observation against all preceding gates."""
    if not all(isinstance(item, dict) for item in (
        runtime, image, python, os_evidence, source,
    )):
        raise BinaryEvidenceError("evidence document is not an object")
    if not isinstance(image_id, str) or not SHA256.fullmatch(image_id):
        raise BinaryEvidenceError("image configuration digest is malformed")

    # Re-run the prior OS verifier, not merely a hash/label comparison: this
    # validates the image, source, Python manifest and exact known Void gap.
    machine = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}.get(image.get("platform"))
    if machine is None:
        raise BinaryEvidenceError("unexpected local image platform")
    known_void_runtime = {
        "schema": "goreecloud.search.runtime-os-registry-unavailable.v1",
        "os": "linux", "machine": machine,
        "release": {"id": "void", "version_id": None},
        "package_manager": "xbps", "package_inventory_status": "unavailable",
        "reason": "runtime_xbps_package_registry_removed",
    }
    expected_os_evidence = verify_previous_os_chain(
        known_void_runtime, image, python, source, sha, image_id,
    )
    if os_evidence != expected_os_evidence:
        raise BinaryEvidenceError("previous Void registry-gap evidence changed")

    if (set(runtime) != {"schema", "os", "machine", "selection", "files", "total_bytes_hashed"}
            or runtime.get("schema") != "goreecloud.search.runtime-selected-elf-hashes.v1"
            or runtime.get("os") != "linux"
            or runtime.get("machine") != machine
            or runtime.get("selection") != SELECTION):
        raise BinaryEvidenceError("runtime ELF selection or architecture mismatches")
    files = runtime.get("files")
    if not isinstance(files, list) or not 1 < len(files) <= MAX_FILES:
        raise BinaryEvidenceError("selected ELF file count is outside bounded limits")
    seen: list[str] = []
    total_bytes = 0
    for record in files:
        if not isinstance(record, dict) or set(record) != {"path", "size_bytes", "sha256"}:
            raise BinaryEvidenceError("runtime ELF record fields are invalid")
        path, size, digest = record["path"], record["size_bytes"], record["sha256"]
        if not isinstance(path, str) or not any(
            path.startswith(prefix)
            and FILE_NAME.fullmatch(path[len(prefix):])
            and matcher.fullmatch(path[len(prefix):])
            for prefix, matcher in PATH_MATCHERS
        ):
            raise BinaryEvidenceError("runtime ELF path outside selected fixed paths")
        if type(size) is not int or not 4 <= size <= MAX_FILE_BYTES:
            raise BinaryEvidenceError("runtime ELF size is invalid")
        if not isinstance(digest, str) or not HEX_HASH.fullmatch(digest):
            raise BinaryEvidenceError("runtime ELF SHA-256 is malformed")
        seen.append(path)
        total_bytes += size
        if total_bytes > MAX_TOTAL_BYTES:
            raise BinaryEvidenceError("selected ELF total exceeds bounded byte budget")
    if seen != sorted(set(seen)):
        raise BinaryEvidenceError("runtime ELF paths are duplicate or unsorted")
    if "/usr/bin/busybox" not in seen or not any(p.startswith("/usr/lib/") for p in seen):
        raise BinaryEvidenceError("required ELF observation coverage is missing")
    if type(runtime.get("total_bytes_hashed")) is not int or runtime["total_bytes_hashed"] != total_bytes:
        raise BinaryEvidenceError("ELF observation total bytes mismatch")

    return {
        "schema": "goreecloud.search.local-selected-elf-file-hash-evidence.v1",
        "repository": REPO_URL,
        "source_commit": sha,
        "source_tree": source["source_tree"],
        "local_image_config_digest": image_id,
        "image_tag": image["image_tag"],
        "platform": image["platform"],
        "os_release": {"id": "void", "version_id": None},
        "package_manager": "xbps",
        "package_inventory_status": "unavailable",
        "previous_os_evidence_sha256": hashlib.sha256(_canonical(os_evidence)).hexdigest(),
        "selection": SELECTION,
        "file_count": len(files),
        "total_bytes_hashed": total_bytes,
        "selected_file_manifest_sha256": hashlib.sha256(_canonical(files)).hexdigest(),
        "files": files,
        "unsigned": True,
        "evidence_scope": "isolated_local_image_selected_regular_elf_file_content_hashes_only",
        "not_evaluated": [
            "complete_installed_os_package_names_versions_or_provenance",
            "all_runtime_executables_libraries_symlinks_or_elf_dependency_closure",
            "complete_spdx_cyclonedx_sbom_dependencies_licenses_or_vulnerabilities",
            "base_image_digest_pin_or_reproducible_build",
            "cryptographic_attestation_or_signature",
            "registry_manifest_digest_or_rollback_artifact",
            "deployed_image_and_runtime_acceptance",
            "seal_and_anchor_qualification",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--local-image-evidence", type=Path, required=True)
    parser.add_argument("--python-evidence", type=Path, required=True)
    parser.add_argument("--os-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = collect(REPO, args.expected_sha)
        image = load_bounded_json(args.local_image_evidence.read_bytes())
        python = load_bounded_json(args.python_evidence.read_bytes())
        os_evidence = load_bounded_json(args.os_evidence.read_bytes())
        runtime = load_bounded_json(sys.stdin.buffer.read(MAX_JSON_BYTES + 1))
        record = verify(runtime, image, python, os_evidence, source, args.expected_sha, args.image_id)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True, indent=2)
            stream.write("\n")
    except (BinaryEvidenceError, OSPackageEvidenceError, BaselineError,
            OSError, ValueError, TypeError):
        parser.exit(2, "LOCAL_SELECTED_ELF_HASH_EVIDENCE_BLOCKED: cannot bind partial runtime evidence\n")
    print("LOCAL_SELECTED_ELF_HASHES_PASS: unsigned selected files only; Void package inventory unavailable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
