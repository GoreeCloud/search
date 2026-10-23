"""Offline, real-Git regressions for source-only release evidence."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "source_baseline_inventory", ROOT / "scripts/source_baseline_inventory.py",
)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def run(repo, *args):
    return subprocess.run(
        ("git", "-C", str(repo), *args), check=True,
        capture_output=True, text=True,
    ).stdout.strip()


class SourceBaselineInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        run(self.repo, "init", "-q")
        run(self.repo, "config", "user.name", "Source Baseline Fixture")
        run(self.repo, "config", "user.email", "fixture@example.invalid")
        run(self.repo, "remote", "add", "origin", inventory.REPO_URL + ".git")
        for name in inventory.RELEASE_INPUTS:
            target = self.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixed synthetic input\n", encoding="utf-8")
        run(self.repo, "add", ".")
        run(self.repo, "commit", "-qm", "source-only fixture")
        self.sha = run(self.repo, "rev-parse", "HEAD")

    def test_clean_commit_has_deterministic_content_only_identity(self):
        first = inventory.collect(self.repo, self.sha)
        self.assertEqual(first, inventory.collect(self.repo, self.sha))
        self.assertEqual(self.sha, first["source_commit"])
        self.assertEqual(run(self.repo, "rev-parse", "HEAD^{tree}"), first["source_tree"])
        self.assertEqual(set(inventory.RELEASE_INPUTS), set(first["input_sha256"]))
        self.assertEqual("exact_clean_source_checkout_only", first["evidence_scope"])
        self.assertIn("seal_and_anchor_qualification", first["not_evaluated"])
        self.assertNotIn("release_stage", first)
        self.assertNotIn("image_digest", first)

    def test_mismatched_commit_and_invalid_sha_block(self):
        with self.assertRaises(inventory.BaselineError):
            inventory.collect(self.repo, "0" * 40)
        with self.assertRaises(inventory.BaselineError):
            inventory.collect(self.repo, "not-a-commit")

    def test_unapproved_repository_identity_blocks(self):
        run(self.repo, "remote", "set-url", "origin",
            "https://github.com/GoreeWorks/search.git")
        with self.assertRaisesRegex(inventory.BaselineError, "origin"):
            inventory.collect(self.repo, self.sha)

    def test_dirty_checkout_does_not_disclose_private_paths(self):
        name = "sensitive-query-and-authorization-token.txt"
        (self.repo / name).write_text("synthetic secret material", encoding="utf-8")
        with self.assertRaises(inventory.BaselineError) as error:
            inventory.collect(self.repo, self.sha)
        self.assertNotIn(name, str(error.exception))

    def test_missing_required_input_blocks(self):
        name = inventory.RELEASE_INPUTS[0]
        (self.repo / name).unlink()
        with self.assertRaises(inventory.BaselineError):
            inventory.collect(self.repo, self.sha)

    def test_modified_tracked_input_blocks(self):
        name = inventory.RELEASE_INPUTS[-1]
        (self.repo / name).write_text("uncommitted mutation", encoding="utf-8")
        with self.assertRaisesRegex(inventory.BaselineError, "clean"):
            inventory.collect(self.repo, self.sha)


if __name__ == "__main__":
    unittest.main()
