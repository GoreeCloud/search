#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Audit an exact Search main/stack-root/Development merge without moving refs.

Requires all Git objects to be available locally. `git merge-tree` may create
unreachable temporary Git objects, but never updates branches, the index or a
worktree. The result is a *blocker report*, not a merge plan or release permit.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


SHA = re.compile(r"[0-9a-f]{40}\Z")
ORIGINS = frozenset({
    "https://github.com/GoreeCloud/search",
    "https://github.com/GoreeCloud/search.git",
    "git@github.com:GoreeCloud/search.git",
})
MAX_OUTPUT = 2_000_000
MAX_PATHS = 5000


class MergePreviewError(Exception):
    """The submitted source boundaries cannot be safely audited."""


def _sha(value: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise MergePreviewError("expected a complete lowercase 40-digit Git SHA")
    return value


def _git(repo: Path, *arguments: str, valid=(0,)) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(("git", "-C", str(repo), *arguments),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=30,
                                env={**os.environ, "GIT_NO_LAZY_FETCH": "1"})
    except (OSError, subprocess.TimeoutExpired):
        raise MergePreviewError("local Git audit is unavailable") from None
    if result.returncode not in valid or len(result.stdout) > MAX_OUTPUT:
        # Never echo Git output, auth/helper material, or arbitrary path names.
        raise MergePreviewError("Git objects or exact-source audit are unavailable")
    return result


def _text(repo: Path, *args: str) -> str:
    try:
        return _git(repo, *args).stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise MergePreviewError("Git identity output is not UTF-8") from None


def _paths(payload: bytes) -> list[str]:
    if payload and not payload.endswith(b"\0"):
        raise MergePreviewError("Git path output was truncated")
    try:
        paths = [entry.decode("utf-8") for entry in payload.split(b"\0") if entry]
    except UnicodeDecodeError:
        raise MergePreviewError("Git path output is not UTF-8") from None
    if len(paths) > MAX_PATHS or len(paths) != len(set(paths)):
        raise MergePreviewError("Git path inventory is too large or duplicated")
    if any(not p or "\x00" in p for p in paths):
        raise MergePreviewError("Git path is invalid")
    return paths


def _preview(repo: Path, main: str, head: str) -> dict:
    raw = _git(repo, "merge-tree", "--write-tree", "--name-only",
               "--no-messages", "-z", main, head, valid=(0, 1))
    tokens = _paths(raw.stdout)
    if not tokens or not SHA.fullmatch(tokens[0]):
        raise MergePreviewError("merge-tree did not return an exact tree identity")
    conflicts = tokens[1:]
    if (raw.returncode == 1 and not conflicts) or (raw.returncode == 0 and conflicts):
        raise MergePreviewError("merge-tree result was internally inconsistent")
    return {
        "merge_tree": tokens[0],
        "clean_three_way_merge": raw.returncode == 0,
        "conflicting_paths": conflicts,
    }


def inspect(repo: Path, expected_main: str, expected_root: str, expected_dev: str) -> dict:
    """Require current clean Development HEAD and exact local Git ancestry."""
    main, root, dev = map(_sha, (expected_main, expected_root, expected_dev))
    if len({main, root, dev}) != 3:
        raise MergePreviewError("main, root and Development identities must differ")
    if _text(repo, "remote", "get-url", "origin") not in ORIGINS:
        raise MergePreviewError("Git origin is not GoreeCloud/search")
    if _text(repo, "rev-parse", "HEAD") != dev:
        raise MergePreviewError("checkout does not match the expected Development head")
    if _git(repo, "status", "--porcelain", "--untracked-files=normal").stdout:
        raise MergePreviewError("source checkout is not clean")
    for sha in (main, root, dev):
        if _text(repo, "cat-file", "-t", sha) != "commit":
            raise MergePreviewError("one expected Git identity is not a commit")
    ancestry = _git(repo, "merge-base", "--is-ancestor", root, dev, valid=(0, 1))
    if ancestry.returncode != 0:
        raise MergePreviewError("stack root is NOT an ancestor of current Development")
    common_main_root = _text(repo, "merge-base", main, root)
    common_main_dev = _text(repo, "merge-base", main, dev)
    if not SHA.fullmatch(common_main_root) or common_main_root != common_main_dev:
        raise MergePreviewError("root/Development do not share the expected main merge base")

    main_delta = _paths(_git(repo, "diff", "--no-renames", "--name-only", "-z",
                             common_main_dev, main).stdout)
    new_since_root = _paths(_git(repo, "diff", "--no-renames", "--name-only", "-z",
                                 root, dev).stdout)
    root_preview = _preview(repo, main, root)
    dev_preview = _preview(repo, main, dev)
    reasons = ["full Seal/Anchor qualification and release authorization not evaluated"]
    if set(main_delta) != {"README.md"}:
        reasons.append("main-side changes are not confined to the known README conflict")
    if root_preview["conflicting_paths"]:
        reasons.append("root PR has unresolved exact main merge conflicts")
    if dev_preview["conflicting_paths"]:
        reasons.append("integrated Development has unresolved exact main merge conflicts")
    reasons.append("README meaning, independent stacked patches and required release gates need review")
    return {
        "schema": "goreecloud.search.exact-merge-preview.v1",
        "repository": "GoreeCloud/search",
        "input_scope": "caller_verified_exact_Git_commits_in_clean_authorized_local_checkout",
        "source_dev": dev,
        "source_main": main,
        "source_stack_root": root,
        "common_main_ancestor": common_main_dev,
        "stack_root_is_dev_ancestor": True,
        "main_changed_paths_since_common_ancestor": main_delta,
        "development_changed_paths_since_stack_root_count": len(new_since_root),
        "root_main_preview": root_preview,
        "development_main_preview": dev_preview,
        "release_decision": "HOLD_NO_PROMOTION_OR_AUTOMATIC_CONFLICT_RESOLUTION",
        "blocking_reasons": reasons,
        "not_evaluated": [
            "semantic_README_reconciliation_and_all_legacy_work",
            "independent_PR_commit_inclusion_and_review_threads",
            "signed_artifact_or_production_security_recovery_acceptance",
            "branch_protection_and_required_release_approval",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--root-pr-sha", required=True)
    parser.add_argument("--development-sha", required=True)
    parser.add_argument("--output", type=Path, help="new JSON path; existing files never overwritten")
    args = parser.parse_args(argv)
    try:
        record = inspect(args.repo, args.main_sha, args.root_pr_sha, args.development_sha)
        output = json.dumps(record, sort_keys=True, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(output)
        else:
            print(output, end="")
    except (MergePreviewError, OSError, ValueError, FileExistsError) as error:
        # stdout/embedded inputs may be sensitive in Git errors; keep bounded.
        message = str(error) if isinstance(error, MergePreviewError) else "safe output unavailable"
        parser.exit(2, f"RELEASE_MERGE_PREVIEW_BLOCKED: {message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
