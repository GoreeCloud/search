#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Inventory an exact, clean Search source checkout; never certify a release.

This offline command neither builds nor deploys. A source inventory is not
cryptographic build provenance, runtime acceptance, Seal, or Anchor evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


REPO = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/GoreeCloud/search"
ALLOWED_ORIGINS = (
    REPO_URL,
    REPO_URL + ".git",
    "git@github.com:GoreeCloud/search.git",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")
RELEASE_INPUTS = (
    ".dockerignore",
    ".github/workflows/native-search-development.yml",
    ".github/workflows/search-foundation.yml",
    "configs/goreecloud/settings.free-first.yml",
    "container/builder.dockerfile",
    "container/builder.dockerfile.dockerignore",
    "container/dist.dockerfile",
    "deploy/vps/compose.free-metasearch-working.yaml",
    "requirements.txt",
    "requirements-server.txt",
    "scripts/build_pinned_staging_image.sh",
    "scripts/audit_dockerfile_base_refs.py",
    "scripts/build_native_linux_service.py",
    "scripts/candidate_image_evidence.py",
    "scripts/free_upgrade_preflight.py",
    "scripts/runtime_python_inventory.py",
    "scripts/verify_runtime_python_inventory.py",
    "scripts/runtime_os_inventory.py",
    "scripts/verify_runtime_os_inventory.py",
    "scripts/runtime_binary_hash_inventory.py",
    "scripts/verify_runtime_binary_hash_inventory.py",
)


class BaselineError(Exception):
    """An exact-source evidence prerequisite is missing or untrusted."""


def git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ("git", "--no-optional-locks", "-C", str(repo), *args), check=True,
            capture_output=True, text=True, timeout=15,
            # A local replace ref can rewrite HEAD^{tree} without changing
            # the caller-supplied commit SHA. Inspect literal Git objects.
            env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1",
                 "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Never echo Git stderr, remote URLs, or untracked filenames.
        raise BaselineError("source checkout could not be verified") from None
    return result.stdout.strip()


def collect(repo: Path, expected_sha: str) -> dict:
    """Return source-only evidence, refusing dirty or ambiguous checkouts."""
    if not SHA.fullmatch(expected_sha):
        raise BaselineError("expected exact 40-character lowercase commit SHA")
    if git(repo, "remote", "get-url", "origin") not in ALLOWED_ORIGINS:
        raise BaselineError("origin is not the authorized GoreeCloud/search repository")
    head = git(repo, "rev-parse", "HEAD")
    if head != expected_sha:
        raise BaselineError("checked-out source differs from expected commit")
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    if not SHA.fullmatch(tree):
        raise BaselineError("Git tree identity is invalid")
    if git(repo, "status", "--porcelain", "--untracked-files=normal"):
        raise BaselineError("source checkout is not clean")

    inputs = {}
    for name in RELEASE_INPUTS:
        path = repo / name
        if git(repo, "ls-files", "--error-unmatch", "--", name) != name:
            raise BaselineError("required release input is not tracked")
        if path.is_symlink() or not path.is_file():
            raise BaselineError("required release input is missing or a symlink")
        inputs[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    return {
        "schema": "goreecloud.search.source-baseline.v1",
        "repository": REPO_URL,
        "source_commit": head,
        "source_tree": tree,
        "input_sha256": inputs,
        "evidence_scope": "exact_clean_source_checkout_only",
        "not_evaluated": [
            "artifact_or_image_digest",
            "build_attestation_or_signature",
            "runtime_and_provider_reliability",
            "native_platform_and_gc_ui_acceptance",
            "security_privacy_and_nine_system_integration",
            "restore_rollback_and_production_acceptance",
            "seal_and_anchor_qualification",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, help="create a new JSON evidence file")
    args = parser.parse_args(argv)
    try:
        payload = collect(REPO, args.expected_sha)
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.output:
            # Never overwrite an existing report or another artifact.
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
        else:
            print(serialized, end="")
    except (BaselineError, FileExistsError, FileNotFoundError, PermissionError) as error:
        parser.exit(2, f"SOURCE_BASELINE_BLOCKED: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
