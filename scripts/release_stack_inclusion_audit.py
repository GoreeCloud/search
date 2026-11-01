#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fail-closed, offline Search open-PR inclusion audit for one exact Development SHA.

Consumes a complete caller-verified authorized GitHub REST open-PR export. Git
commands are read-only, never update refs and never fetch missing objects.
Exact commit ancestry is stronger than patch-ID equivalence; neither proves
semantic feature parity or permits a merge, release, or conflict resolution.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from release_pr_graph_inventory import InventoryError, _read_json, inventory


SHA = re.compile(r"[0-9a-f]{40}\Z")
CHERRY = re.compile(r"([+-]) ([0-9a-f]{40})(?: [^\n]*)?\Z")
ORIGINS = frozenset({
    "https://github.com/GoreeCloud/search",
    "https://github.com/GoreeCloud/search.git",
    "git@github.com:GoreeCloud/search.git",
})
MAX_OUTPUT_BYTES = 4_000_000
MAX_PATHS = 2500
MAX_PR_COMMITS = 2000


class InclusionError(Exception):
    """The exact, complete evidence required for an inclusion audit is absent."""


def _sha(value: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise InclusionError("expected an exact 40-character lowercase Git commit SHA")
    return value


def _git(repo: Path, *args: str, valid=(0,)) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0",
           "GIT_NO_REPLACE_OBJECTS": "1"}
    try:
        process = subprocess.run(
            ("git", "--no-optional-locks", "-C", str(repo), *args),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            timeout=60, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise InclusionError("local read-only Git audit unavailable") from None
    if process.returncode not in valid or len(process.stdout) > MAX_OUTPUT_BYTES:
        # Never emit arbitrary Git stderr, credential helpers, or file contents.
        raise InclusionError("Git object unavailable or exact-source check failed")
    return process


def _text(repo: Path, *args: str) -> str:
    try:
        return _git(repo, *args).stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise InclusionError("Git identity output is not UTF-8") from None


def _paths(data: bytes, *, deduplicate: bool = False) -> list[str]:
    if data and not data.endswith(b"\0"):
        raise InclusionError("Git path output was incomplete")
    try:
        paths = [part.decode("utf-8") for part in data.split(b"\0") if part]
    except UnicodeDecodeError:
        raise InclusionError("Git file paths are not UTF-8") from None
    if len(paths) > MAX_PATHS * 20:
        raise InclusionError("Git changed-path records exceed bounded audit")
    if deduplicate:
        paths = sorted(set(paths))
    if len(paths) > MAX_PATHS or len(paths) != len(set(paths)):
        raise InclusionError("Git changed-path inventory is too large or repeated")
    return paths


def _count(repo: Path, *args: str) -> int:
    count = _text(repo, "rev-list", "--count", *args)
    if not count.isdecimal() or int(count) > MAX_PR_COMMITS:
        raise InclusionError("PR introduces an excessive or invalid commit count")
    return int(count)


def _patches(repo: Path, dev: str, head: str, base: str) -> tuple[list[str], list[str]]:
    # `git cherry` omits commits already reachable by SHA from Development.
    # Count only the right-only nonmerge commits or very old parent branches
    # would falsely appear to contribute thousands of pending commits.
    expected = _count(repo, "--no-merges", f"{base}..{head}", "--not", dev)
    try:
        lines = _git(repo, "cherry", "-v", dev, head, base).stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        raise InclusionError("Git cherry output is not UTF-8") from None
    matched, unmatched = [], []
    for line in lines:
        match = CHERRY.fullmatch(line)
        if match is None:
            raise InclusionError("Git cherry output is ambiguous")
        (matched if match.group(1) == "-" else unmatched).append(match.group(2))
    if len(lines) != expected or len(set(matched + unmatched)) != len(lines):
        raise InclusionError("Git cherry did not account for every PR nonmerge commit")
    return matched, unmatched


def audit(prs: object, repo: Path, expected_dev: str, expected_main: str,
          expected_pr_count: int) -> dict:
    """Prove ancestry or disclose the exact PR-scoped missing patch identities."""
    dev, main = _sha(expected_dev), _sha(expected_main)
    if isinstance(expected_pr_count, bool) or not isinstance(expected_pr_count, int) or not (1 <= expected_pr_count < 100):
        raise InclusionError("expected PR count must be in the single-page 1-99 range")
    graph = inventory(prs, dev, main)
    if graph["statistics"]["open_prs"] != expected_pr_count:
        raise InclusionError("GitHub PR snapshot does not match expected open-PR count")
    if graph["unattached_prs"] or graph["cycle_prs"] or not graph["development_path_to_main"]:
        raise InclusionError("open-PR graph has unattached refs, cycles or no Development lineage")
    # Historical GitHub base SHA drift can coexist with a sound branch graph;
    # disclose it rather than discarding patch-inclusion evidence altogether.
    if _text(repo, "remote", "get-url", "origin") not in ORIGINS:
        raise InclusionError("Git origin is not authorized GoreeCloud/search")
    if _text(repo, "rev-parse", "HEAD") != dev:
        raise InclusionError("checkout does not match expected Development SHA")
    if _git(repo, "status", "--porcelain", "--untracked-files=normal").stdout:
        raise InclusionError("Development source checkout is not clean")
    for sha in {main, dev, *(row["head_sha"] for row in graph["pull_requests"]),
                *(row["base_sha"] for row in graph["pull_requests"])}:
        if _text(repo, "cat-file", "-t", sha) != "commit":
            raise InclusionError("expected PR/Git head identity is not a commit")

    rows = []
    all_unmatched: set[str] = set()
    all_matched: set[str] = set()
    for entry in graph["pull_requests"]:
        number, head, base = entry["number"], entry["head_sha"], entry["base_sha"]
        ancestor = _git(repo, "merge-base", "--is-ancestor", head, dev, valid=(0, 1))
        row = {
            "pr": number, "head_sha": head, "recorded_base_sha": base,
            "head_is_exact_development_ancestor": ancestor.returncode == 0,
        }
        if ancestor.returncode == 0:
            row["inclusion_class"] = "EXACT_COMMIT_ANCESTOR"
        else:
            # The historical/current REST base may be newer than the PR head;
            # use their exact common ancestor to scope introduced commits.
            common = _text(repo, "merge-base", base, head)
            if not SHA.fullmatch(common):
                raise InclusionError("PR head/base lacks an unambiguous common ancestor")
            merges = _count(repo, "--merges", f"{common}..{head}", "--not", dev)
            matched, unmatched = _patches(repo, dev, head, common)
            # `base..head` tree diff can include thousands of commits already
            # in Development when a legacy PR has a very old recorded base.
            # Only paths touched by *right-only* nonmerge commits are relevant.
            paths = _paths(_git(repo, "log", "--no-merges", "--format=", "--name-only", "-z",
                                "--no-ext-diff", "--no-textconv", "--no-renames",
                                f"{common}..{head}", "--not", dev).stdout,
                           deduplicate=True)
            # Exact file-tip equality, not semantic coverage. Compare only
            # files modified by the PR against the current Development tree.
            differing = set(_paths(_git(repo, "diff", "--no-ext-diff", "--no-textconv",
                                        "--no-renames", "--name-only", "-z", dev, head).stdout))
            row.update({
                "inclusion_class": (
                    "UNASSESSED_MERGE_COMMITS" if merges else
                    "PATCH_EQUIVALENT_ONLY" if not unmatched else "UNMATCHED_PR_PATCHES"
                ),
                "scope_common_ancestor": common,
                "nonancestor_pr_nonmerge_commits": len(matched) + len(unmatched),
                "scoped_merge_commits_needing_review": merges,
                "matching_patch_ids_commit_shas": matched,
                "unmatched_patch_ids_commit_shas": unmatched,
                "pr_right_only_commit_changed_paths": paths,
                "pr_right_only_paths_equal_at_tips": sorted(set(paths) - differing),
                "pr_right_only_paths_different_at_tips": sorted(set(paths) & differing),
            })
            all_matched.update(matched)
            all_unmatched.update(unmatched)
        rows.append(row)

    nonancestors = [row for row in rows if not row["head_is_exact_development_ancestor"]]
    return {
        "schema": "goreecloud.search.exact-stack-inclusion.v1",
        "repository": "GoreeCloud/search",
        "evidence_scope": "caller_verified_complete_GitHub_open_PR_export_and_exact_offline_local_Git_objects",
        "source_dev": dev, "source_main": main,
        "base_sha_drift": graph["base_sha_drift"],
        "statistics": {
            "open_prs_audited": len(rows),
            "exact_ancestor_prs": len(rows) - len(nonancestors),
            "nonancestor_prs": len(nonancestors),
            "nonancestor_prs_with_unmatched_patches": sum(bool(r.get("unmatched_patch_ids_commit_shas")) for r in nonancestors),
            "scoped_unmatched_patch_instances": sum(len(r.get("unmatched_patch_ids_commit_shas", [])) for r in nonancestors),
            "distinct_unmatched_commit_shas": len(all_unmatched),
            "distinct_patch_equivalent_commit_shas": len(all_matched),
            "base_sha_drift_edges": len(graph["base_sha_drift"]),
        },
        "pull_requests": rows,
        "release_decision": "HOLD_NO_PROMOTION_OR_AUTOMATIC_CONFLICT_RESOLUTION",
        "blocking_reasons": [
            "nonancestor PR patch inclusion and semantics require deliberate independent review" if nonancestors else
            "commit inclusion is not a substitute for release qualification",
            "main README merge conflict remains a separately controlled release-line decision",
            "recorded PR base-SHA drift requires review" if graph["base_sha_drift"] else
            "reconfirm exact PR base-SHA identities before any merge",
            "Seal/Anchor security, provenance, native-platform and production acceptance not evaluated",
        ],
        "interpretation": (
            "Ancestry is exact commit inclusion. Matching Git patch-ID is weaker than semantic equivalence; "
            "unmatched patch-ID does not establish semantic feature absence. Identical/different changed-file "
            "tips do not establish historical change inclusion. Merge commits require separate review."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="complete caller-verified GoreeCloud/search REST open-PR JSON list")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--development-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--expected-pr-count", required=True, type=int)
    parser.add_argument("--output", type=Path, help="exclusive-create report; never overwrite")
    args = parser.parse_args(argv)
    try:
        result = audit(_read_json(args.input), args.repo, args.development_sha,
                       args.main_sha, args.expected_pr_count)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(rendered)
        else:
            print(rendered, end="")
    except (InclusionError, InventoryError, FileExistsError, FileNotFoundError, OSError) as error:
        reason = str(error) if isinstance(error, (InclusionError, InventoryError)) else "safe input/output unavailable"
        parser.exit(2, f"RELEASE_STACK_INCLUSION_BLOCKED: {reason}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
