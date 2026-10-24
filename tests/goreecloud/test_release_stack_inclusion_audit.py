"""Offline, real-Git regression tests for exact open-PR patch inclusion checks."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import release_stack_inclusion_audit as audit  # noqa: E402


def _run(repo, *args):
    cmd = subprocess.run(["git", "-C", str(repo), *args], text=True,
                         capture_output=True, check=False)
    if cmd.returncode != 0:
        raise AssertionError(f"git {args!r} failed: {cmd.stderr}")
    return cmd.stdout.strip()


def _commit(repo, name, text):
    (repo / name).write_text(text, encoding="utf-8")
    _run(repo, "add", name)
    _run(repo, "commit", "-m", name)
    return _run(repo, "rev-parse", "HEAD")


def _pr(number, head_ref, head_sha, base_ref, base_sha):
    return {
        "number": number, "state": "open", "draft": True,
        "head": {"ref": head_ref, "sha": head_sha,
                 "repo": {"full_name": "GoreeCloud/search"}},
        "base": {"ref": base_ref, "sha": base_sha,
                 "repo": {"full_name": "GoreeCloud/search"}},
    }


class ReleaseStackInclusionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        _run(self.repo, "init", "-b", "main")
        _run(self.repo, "config", "user.name", "Search Audit")
        _run(self.repo, "config", "user.email", "test@example.invalid")
        _run(self.repo, "remote", "add", "origin", "https://github.com/GoreeCloud/search.git")
        self.main = _commit(self.repo, "README.md", "initial\n")

        _run(self.repo, "switch", "-c", "deploy/search-vps-private-20261017")
        self.root = _commit(self.repo, "root.txt", "root\n")

        _run(self.repo, "switch", "-c", "feature/searxng-goreecloud-foundation-20261010", self.main)
        self.missing = _commit(self.repo, "independent.txt", "not yet integrated\n")

        _run(self.repo, "switch", "-c", "stabilize/search-ci-exact-head-20261013", self.main)
        self.equivalent = _commit(self.repo, "equivalent.txt", "same patch\n")

        _run(self.repo, "switch", "-c", audit.inventory.__globals__["DEV_REF"], self.root)
        _commit(self.repo, "development.txt", "integrated work\n")
        _run(self.repo, "cherry-pick", self.equivalent)
        self.dev = _run(self.repo, "rev-parse", "HEAD")
        self.prs = [
            _pr(22, "deploy/search-vps-private-20261017", self.root, "main", self.main),
            _pr(2, "feature/searxng-goreecloud-foundation-20261010", self.missing,
                "main", self.main),
            _pr(4, "stabilize/search-ci-exact-head-20261013", self.equivalent,
                "main", self.main),
            _pr(71, audit.inventory.__globals__["DEV_REF"], self.dev,
                "deploy/search-vps-private-20261017", self.root),
        ]

    def audit(self):
        return audit.audit(self.prs, self.repo, self.dev, self.main, 4)

    def test_real_ancestry_exact_pr_scoped_patch_and_file_tip_evidence(self):
        result = self.audit()
        rows = {row["pr"]: row for row in result["pull_requests"]}
        self.assertEqual(4, result["statistics"]["open_prs_audited"])
        self.assertEqual(2, result["statistics"]["exact_ancestor_prs"])
        self.assertEqual(2, result["statistics"]["nonancestor_prs"])
        self.assertEqual("EXACT_COMMIT_ANCESTOR", rows[71]["inclusion_class"])
        self.assertEqual("EXACT_COMMIT_ANCESTOR", rows[22]["inclusion_class"])
        self.assertEqual("UNMATCHED_PR_PATCHES", rows[2]["inclusion_class"])
        self.assertEqual([self.missing], rows[2]["unmatched_patch_ids_commit_shas"])
        self.assertEqual(["independent.txt"], rows[2]["pr_right_only_paths_different_at_tips"])
        self.assertEqual("PATCH_EQUIVALENT_ONLY", rows[4]["inclusion_class"])
        self.assertEqual([self.equivalent], rows[4]["matching_patch_ids_commit_shas"])
        self.assertEqual(["equivalent.txt"], rows[4]["pr_right_only_paths_equal_at_tips"])
        self.assertEqual(1, result["statistics"]["distinct_unmatched_commit_shas"])
        self.assertEqual("HOLD_NO_PROMOTION_OR_AUTOMATIC_CONFLICT_RESOLUTION",
                         result["release_decision"])

    def test_snapshot_length_and_head_provenance_require_exact_match(self):
        with self.assertRaisesRegex(audit.InclusionError, "expected open-PR count"):
            audit.audit(self.prs, self.repo, self.dev, self.main, 3)
        with self.assertRaisesRegex(audit.InventoryError, "Development PR source"):
            audit.audit(self.prs, self.repo, "f" * 40, self.main, 4)

    def test_dirty_or_wrong_checkout_or_foreign_origin_fails_closed(self):
        (self.repo / "new-artifact.txt").write_text("not committed\n", encoding="utf-8")
        with self.assertRaisesRegex(audit.InclusionError, "not clean"):
            self.audit()
        (self.repo / "new-artifact.txt").unlink()
        _run(self.repo, "remote", "set-url", "origin", "https://github.com/Other/search.git")
        with self.assertRaisesRegex(audit.InclusionError, "origin"):
            self.audit()
        _run(self.repo, "remote", "set-url", "origin", "https://github.com/GoreeCloud/search.git")
        _run(self.repo, "switch", "main")
        with self.assertRaisesRegex(audit.InclusionError, "expected Development"):
            self.audit()

    def test_missing_git_object_fails_closed_not_report_as_unmatched(self):
        self.prs[1]["head"]["sha"] = "f" * 40
        with self.assertRaisesRegex(audit.InclusionError, "Git object unavailable"):
            self.audit()

    def test_cli_never_overwrites_an_existing_report(self):
        snapshot = Path(self.temp.name) / "snapshot.json"
        report = Path(self.temp.name) / "result.json"
        snapshot.write_text(json.dumps(self.prs), encoding="utf-8")
        cmd = [sys.executable, str(ROOT / "scripts/release_stack_inclusion_audit.py"),
               "--input", str(snapshot), "--repo", str(self.repo),
               "--development-sha", self.dev, "--main-sha", self.main,
               "--expected-pr-count", "4", "--output", str(report)]
        first = subprocess.run(cmd, text=True, capture_output=True, check=False)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(4, json.loads(report.read_text())["statistics"]["open_prs_audited"])
        second = subprocess.run(cmd, text=True, capture_output=True, check=False)
        self.assertEqual(2, second.returncode)
        self.assertIn("RELEASE_STACK_INCLUSION_BLOCKED", second.stderr)


if __name__ == "__main__":
    unittest.main()
