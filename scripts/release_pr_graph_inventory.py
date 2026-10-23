#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Inspect an authorized GitHub Search PR-list JSON export, without changing Git.

The caller supplies one complete `GET /repos/GoreeCloud/search/pulls?state=open`
response from the authorized GoreeCloud GitHub connection. This offline tool
does not fetch, retarget, merge, close, or review a PR, nor qualify a release.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


REPOSITORY = "GoreeCloud/search"
SHA = re.compile(r"[0-9a-f]{40}\Z")
REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}\Z")
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_SINGLE_PAGE = 100
DEV_PR = 71
DEV_REF = "feature/search-working-free-sources-20261020"


class InventoryError(Exception):
    """An input is incomplete, ambiguous, or not an authorized Search export."""


def _branch(value: object) -> str:
    if not isinstance(value, str) or not REF.fullmatch(value):
        raise InventoryError("PR branch ref is invalid")
    if ".." in value or "//" in value or value.endswith(("/", ".")):
        raise InventoryError("PR branch ref is ambiguous")
    return value


def _sha(value: object) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise InventoryError("PR or expected Git SHA must have 40 lowercase hexadecimal characters")
    return value


def _endpoint(value: object) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise InventoryError("PR head/base endpoint is missing")
    if not isinstance(value.get("repo"), dict) or value["repo"].get("full_name") != REPOSITORY:
        raise InventoryError("PR endpoint is not the authorized GoreeCloud/search repository")
    return _branch(value.get("ref")), _sha(value.get("sha"))


def _read_json(path: Path) -> object:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_INPUT_BYTES:
            raise InventoryError("input JSON exceeds bounded PR-list size")
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise InventoryError("input is not valid GitHub PR-list JSON") from None


def inventory(prs: object, expected_dev_sha: str, expected_main_sha: str) -> dict:
    """Identify PR stack topology and drift; never infer merge/release readiness."""
    _sha(expected_dev_sha)
    _sha(expected_main_sha)
    if not isinstance(prs, list) or not prs:
        raise InventoryError("expected a nonempty GitHub REST pull-request list")
    if len(prs) >= MAX_SINGLE_PAGE:
        raise InventoryError("single-page PR export may be truncated; inspect all pages")

    nodes: dict[int, dict] = {}
    by_head: dict[str, int] = {}
    for raw in prs:
        if not isinstance(raw, dict):
            raise InventoryError("invalid PR list record")
        number = raw.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            raise InventoryError("PR number is invalid")
        if number in nodes:
            raise InventoryError("duplicate PR number in input")
        if raw.get("state") != "open" or not isinstance(raw.get("draft"), bool):
            raise InventoryError("input includes a closed PR or incomplete draft state")
        head_ref, head_sha = _endpoint(raw.get("head"))
        base_ref, base_sha = _endpoint(raw.get("base"))
        if head_ref == base_ref or head_ref in by_head:
            raise InventoryError("duplicate or self-targeting PR head branch")
        nodes[number] = {
            "number": number, "draft": raw["draft"],
            "head_ref": head_ref, "head_sha": head_sha,
            "base_ref": base_ref, "base_sha": base_sha,
        }
        by_head[head_ref] = number

    development = nodes.get(DEV_PR)
    if not development or development["head_ref"] != DEV_REF:
        raise InventoryError("Development PR #71 is missing or has an unexpected head")
    if development["head_sha"] != expected_dev_sha:
        raise InventoryError("exported Development PR source differs from expected integration head")

    direct_main: list[int] = []
    unattached: list[int] = []
    base_drift: list[dict] = []
    for node in nodes.values():
        if node["base_ref"] == "main":
            direct_main.append(node["number"])
            if node["base_sha"] != expected_main_sha:
                base_drift.append({
                    "pr": node["number"], "parent_pr": None,
                    "target_ref": "main", "recorded_base_sha": node["base_sha"],
                    "current_target_sha": expected_main_sha,
                })
        else:
            parent = by_head.get(node["base_ref"])
            if parent is None:
                unattached.append(node["number"])
            elif node["base_sha"] != nodes[parent]["head_sha"]:
                base_drift.append({
                    "pr": node["number"], "parent_pr": parent,
                    "target_ref": node["base_ref"],
                    "recorded_base_sha": node["base_sha"],
                    "current_target_sha": nodes[parent]["head_sha"],
                })

    paths: dict[int, list[int]] = {}
    cycles: set[int] = set()

    def to_main(number: int, active: tuple[int, ...]) -> list[int] | None:
        if number in paths:
            return paths[number]
        if number in active:
            cycles.update(active[active.index(number):])
            return None
        node = nodes[number]
        if node["base_ref"] == "main":
            path = [number]
        else:
            parent = by_head.get(node["base_ref"])
            if parent is None:
                return None
            parent_path = to_main(parent, (*active, number))
            if parent_path is None:
                return None
            path = [number, *parent_path]
        paths[number] = path
        return path

    for number in sorted(nodes):
        to_main(number, ())

    problems = []
    if base_drift:
        problems.append("PR target branch SHA differs from recorded PR base SHA")
    if unattached:
        problems.append("PR target branch has no matching open PR head")
    if cycles:
        problems.append("cycle in open PR base relationships")
    if not direct_main:
        problems.append("no main-targeting root PR")

    rows = []
    for number in sorted(nodes):
        row = dict(nodes[number])
        row["parent_pr"] = by_head.get(row["base_ref"])
        row["path_to_main"] = paths.get(number)
        rows.append(row)

    return {
        "schema": "goreecloud.search.open-pr-release-line-inventory.v1",
        "repository": REPOSITORY,
        "evidence_scope": "caller_provided_authorized_GitHub_REST_open_PR_list_only",
        "source_expected": expected_dev_sha,
        "main_expected": expected_main_sha,
        "statistics": {
            "open_prs": len(nodes),
            "draft_prs": sum(node["draft"] for node in nodes.values()),
            "main_target_prs": len(direct_main),
            "stacked_target_prs": len(nodes) - len(direct_main),
            "paths_to_main_count": len(paths),
            "base_sha_drift_edges": len(base_drift),
            "unattached_base_refs": len(unattached),
            "cycles": len(cycles),
        },
        "development_path_to_main": paths.get(DEV_PR),
        "main_target_prs": sorted(direct_main),
        "base_sha_drift": sorted(base_drift, key=lambda row: row["pr"]),
        "unattached_prs": sorted(unattached),
        "cycle_prs": sorted(cycles),
        "topology_problems": problems,
        "pull_requests": rows,
        "release_decision": "BLOCKED_NOT_QUALIFIED",
        "not_evaluated": [
            "Git_merge_ancestry_or_unmerged_work_inclusion",
            "individual_PR_mergeability_or_blocking_reviews",
            "repository_branch_protection_and_required_checks",
            "current_release_artifact_or_deployed_image_identity",
            "Seal_Anchor_security_native_platform_and_production_acceptance",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="complete authorized GitHub REST GET /pulls?state=open JSON")
    parser.add_argument("--expected-dev-sha", required=True)
    parser.add_argument("--expected-main-sha", required=True)
    parser.add_argument("--output", type=Path, help="exclusive creation of JSON result")
    args = parser.parse_args(argv)
    try:
        record = inventory(_read_json(args.input), args.expected_dev_sha, args.expected_main_sha)
        rendered = json.dumps(record, indent=2, sort_keys=True) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(rendered)
        else:
            print(rendered, end="")
    except (InventoryError, FileExistsError, FileNotFoundError, OSError) as error:
        if isinstance(error, InventoryError):
            reason = str(error)
        else:
            reason = "input or output could not be safely accessed"
        parser.exit(2, f"RELEASE_PR_GRAPH_BLOCKED: {reason}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
