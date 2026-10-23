"""Read-only offline regression tests for guarded stacked-PR inspection."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import json


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/release_pr_graph_inventory.py"
SPEC = importlib.util.spec_from_file_location("release_pr_graph_inventory", TOOL)
graph = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(graph)

MAIN_SHA = "1" * 40
SHA22 = "2" * 40
SHA70 = "7" * 40
DEV_SHA = "a" * 40


def pr(number, head, sha, base, base_sha, draft=True):
    return {
        "number": number, "draft": draft, "state": "open",
        "head": {"ref": head, "sha": sha, "repo": {"full_name": graph.REPOSITORY}},
        "base": {"ref": base, "sha": base_sha, "repo": {"full_name": graph.REPOSITORY}},
    }


def fixture():
    return [
        pr(22, "deploy/search-vps-private-20261017", SHA22, "main", MAIN_SHA),
        pr(70, "security/search-free-readonly-release-gate-20261020", SHA70,
           "deploy/search-vps-private-20261017", SHA22),
        pr(71, graph.DEV_REF, DEV_SHA,
           "security/search-free-readonly-release-gate-20261020", SHA70),
    ]


class ReleasePRGraphInventoryTests(unittest.TestCase):
    def test_exact_integrated_head_and_stacked_lineage(self):
        result = graph.inventory(fixture(), DEV_SHA, MAIN_SHA)
        self.assertEqual(3, result["statistics"]["open_prs"])
        self.assertEqual(1, result["statistics"]["main_target_prs"])
        self.assertEqual(2, result["statistics"]["stacked_target_prs"])
        self.assertEqual([71, 70, 22], result["development_path_to_main"])
        self.assertEqual([], result["base_sha_drift"])
        self.assertEqual("BLOCKED_NOT_QUALIFIED", result["release_decision"])
        self.assertIn("individual_PR_mergeability_or_blocking_reviews", result["not_evaluated"])

    def test_output_is_deterministic_when_provider_order_changes(self):
        original = fixture()
        self.assertEqual(graph.inventory(original, DEV_SHA, MAIN_SHA),
                         graph.inventory(list(reversed(original)), DEV_SHA, MAIN_SHA))

    def test_discrepant_stacked_and_main_base_sha_are_reported_as_blockers(self):
        records = fixture()
        records[0]["base"]["sha"] = "e" * 40
        records[1]["base"]["sha"] = "f" * 40
        result = graph.inventory(records, DEV_SHA, MAIN_SHA)
        self.assertEqual([22, 70], [x["pr"] for x in result["base_sha_drift"]])
        self.assertEqual(2, result["statistics"]["base_sha_drift_edges"])
        self.assertTrue(result["topology_problems"])
        self.assertEqual("BLOCKED_NOT_QUALIFIED", result["release_decision"])

    def test_missing_parent_is_preserved_not_assumed_to_be_integrated(self):
        records = fixture()
        records[1]["base"]["ref"] = "unknown-unreviewed-base"
        result = graph.inventory(records, DEV_SHA, MAIN_SHA)
        self.assertEqual([70], result["unattached_prs"])
        self.assertIsNone(result["development_path_to_main"])
        self.assertEqual(1, result["statistics"]["unattached_base_refs"])

    def test_cycle_blocks_topological_path(self):
        records = fixture()
        records[0]["base"]["ref"] = graph.DEV_REF
        records[0]["base"]["sha"] = DEV_SHA
        result = graph.inventory(records, DEV_SHA, MAIN_SHA)
        self.assertIsNone(result["development_path_to_main"])
        self.assertEqual(3, result["statistics"]["cycles"])
        self.assertEqual(0, result["statistics"]["main_target_prs"])

    def test_downstream_dependant_is_not_misclassified_as_cycle_member(self):
        records = fixture()
        records[0]["base"]["ref"] = graph.DEV_REF
        records[0]["base"]["sha"] = DEV_SHA
        records.append(pr(4, "review/a-downstream-sibling", "4" * 40,
                          "deploy/search-vps-private-20261017", SHA22))
        result = graph.inventory(records, DEV_SHA, MAIN_SHA)
        self.assertEqual([22, 70, 71], result["cycle_prs"])
        self.assertIsNone(result["pull_requests"][0]["path_to_main"])

    def test_incorrect_expected_development_identity_fails_closed(self):
        with self.assertRaisesRegex(graph.InventoryError, "Development PR source"):
            graph.inventory(fixture(), "f" * 40, MAIN_SHA)
        with self.assertRaises(graph.InventoryError):
            graph.inventory(fixture(), "not-a-sha", MAIN_SHA)

    def test_foreign_repository_and_closed_state_refused(self):
        for change in ("foreign", "closed"):
            records = fixture()
            if change == "foreign":
                records[2]["head"]["repo"]["full_name"] = "Other/search"
            else:
                records[2]["state"] = "closed"
            with self.subTest(change=change), self.assertRaises(graph.InventoryError):
                graph.inventory(records, DEV_SHA, MAIN_SHA)

    def test_duplicate_pr_number_and_head_branch_refused(self):
        records = fixture()
        records.append(pr(71, "a-new-ref", "f" * 40, "main", MAIN_SHA))
        with self.assertRaisesRegex(graph.InventoryError, "duplicate PR number"):
            graph.inventory(records, DEV_SHA, MAIN_SHA)
        records[-1]["number"] = 99
        records[-1]["head"]["ref"] = graph.DEV_REF
        with self.assertRaisesRegex(graph.InventoryError, "duplicate or self-targeting"):
            graph.inventory(records, DEV_SHA, MAIN_SHA)

    def test_single_page_limit_and_malformed_pr_refused(self):
        with self.assertRaisesRegex(graph.InventoryError, "may be truncated"):
            graph.inventory([fixture()[0]] * 100, DEV_SHA, MAIN_SHA)
        records = fixture()
        records[0]["head"]["sha"] = "not-a-sha"
        with self.assertRaises(graph.InventoryError):
            graph.inventory(records, DEV_SHA, MAIN_SHA)
        records = fixture()
        records[0]["head"]["ref"] = "invalid//ref"
        with self.assertRaises(graph.InventoryError):
            graph.inventory(records, DEV_SHA, MAIN_SHA)

    def test_cli_creates_exclusive_read_only_report_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory) / "authorized-open-prs.json"
            out = Path(directory) / "inventory.json"
            src.write_text(json.dumps(fixture()), encoding="utf-8")
            cmd = [sys.executable, str(TOOL), "--input", str(src),
                   "--expected-dev-sha", DEV_SHA,
                   "--expected-main-sha", MAIN_SHA, "--output", str(out)]
            first = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual("BLOCKED_NOT_QUALIFIED", json.loads(out.read_text())["release_decision"])
            second = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(2, second.returncode)
            self.assertIn("RELEASE_PR_GRAPH_BLOCKED", second.stderr)


if __name__ == "__main__":
    unittest.main()
