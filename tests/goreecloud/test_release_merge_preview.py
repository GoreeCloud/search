"""Offline three-way Git ancestry and conflict-preview gate fixtures."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import release_merge_preview as preview


class SyntheticStack:
    def __init__(self, root_changes_readme=True, main_extra_file=False):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.git("init", "-b", "main")
        self.git("remote", "add", "origin", "https://github.com/GoreeCloud/search.git")
        self.write("README.md", "# Search\nBase release note\n")
        self.write("persisted.txt", "unchanged\n")
        self.commit("initial common source")
        self.git("branch", "candidate-root")
        self.git("switch", "candidate-root")
        if root_changes_readme:
            self.write("README.md", "# Search\nRoot Development note\n")
        else:
            self.write("new-root.txt", "approved root changes\n")
        self.commit("stack root")
        self.root = self.git("rev-parse", "HEAD")
        self.git("branch", "integrated-development")
        self.git("switch", "integrated-development")
        self.write("native-service.py", "print('owned fixture')\n")
        self.commit("integrated Development work")
        self.dev = self.git("rev-parse", "HEAD")
        self.git("switch", "main")
        self.write("README.md", "# Search\nCurrent main notice\n")
        if main_extra_file:
            self.write("README.extra", "current main independent work\n")
        self.commit("main notice update")
        self.main = self.git("rev-parse", "HEAD")
        self.git("switch", "integrated-development")

    def git(self, *args):
        result = subprocess.run(("git", "-C", str(self.path), *args),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=True, text=True, timeout=15)
        return result.stdout.strip()

    def write(self, name, contents):
        (self.path / name).write_text(contents, encoding="utf-8")

    def commit(self, message):
        self.git("add", ".")
        self.git("-c", "user.name=Offline Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-m", message)

    def inspect(self):
        return preview.inspect(self.path, self.main, self.root, self.dev)

    def cleanup(self):
        self.temp.cleanup()


class ReleaseMergePreviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SyntheticStack()
        self.addCleanup(self.fixture.cleanup)

    def test_exact_ancestry_and_readme_conflict_report_without_ref_mutation(self):
        before = self.fixture.git("show-ref")
        output = self.fixture.inspect()
        after = self.fixture.git("show-ref")
        self.assertEqual(before, after)
        self.assertEqual("", self.fixture.git("status", "--porcelain"))
        self.assertTrue(output["stack_root_is_dev_ancestor"])
        self.assertEqual(["README.md"], output["main_changed_paths_since_common_ancestor"])
        self.assertEqual(1, output["development_changed_paths_since_stack_root_count"])
        self.assertEqual(["README.md"], output["root_main_preview"]["conflicting_paths"])
        self.assertEqual(["README.md"], output["development_main_preview"]["conflicting_paths"])
        self.assertFalse(output["development_main_preview"]["clean_three_way_merge"])
        self.assertEqual("HOLD_NO_PROMOTION_OR_AUTOMATIC_CONFLICT_RESOLUTION",
                         output["release_decision"])
        self.assertIn("semantic_README_reconciliation_and_all_legacy_work", output["not_evaluated"])

    def test_clean_merge_still_does_not_grant_release_permission(self):
        other = SyntheticStack(root_changes_readme=False)
        self.addCleanup(other.cleanup)
        output = other.inspect()
        self.assertTrue(output["root_main_preview"]["clean_three_way_merge"])
        self.assertTrue(output["development_main_preview"]["clean_three_way_merge"])
        self.assertEqual([], output["development_main_preview"]["conflicting_paths"])
        self.assertEqual("HOLD_NO_PROMOTION_OR_AUTOMATIC_CONFLICT_RESOLUTION",
                         output["release_decision"])

    def test_main_additional_work_is_not_assumed_safe(self):
        other = SyntheticStack(main_extra_file=True)
        self.addCleanup(other.cleanup)
        output = other.inspect()
        self.assertEqual(["README.extra", "README.md"],
                         output["main_changed_paths_since_common_ancestor"])
        self.assertTrue(any("not confined" in reason for reason in output["blocking_reasons"]))

    def test_wrong_development_head_and_dirty_worktree_fail_closed(self):
        with self.assertRaisesRegex(preview.MergePreviewError, "checkout"):
            preview.inspect(self.fixture.path, self.fixture.main, self.fixture.root, "f" * 40)
        self.fixture.write("untracked.tmp", "retain me\n")
        with self.assertRaisesRegex(preview.MergePreviewError, "not clean"):
            self.fixture.inspect()
        self.assertEqual("retain me\n", (self.fixture.path / "untracked.tmp").read_text())

    def test_unknown_origin_and_nonancestor_root_fail_closed(self):
        self.fixture.git("remote", "set-url", "origin", "https://github.com/unrelated/project.git")
        with self.assertRaisesRegex(preview.MergePreviewError, "not GoreeCloud"):
            self.fixture.inspect()
        self.fixture.git("remote", "set-url", "origin", "https://github.com/GoreeCloud/search.git")
        self.fixture.git("switch", "-c", "unrelated-root", self.fixture.main)
        self.fixture.write("unrelated.txt", "unmerged independent work\n")
        self.fixture.commit("independent main descendant")
        independent = self.fixture.git("rev-parse", "HEAD")
        self.fixture.git("switch", "integrated-development")
        with self.assertRaisesRegex(preview.MergePreviewError, "NOT an ancestor"):
            preview.inspect(self.fixture.path, self.fixture.main, independent, self.fixture.dev)

    def test_invalid_shas_and_duplicate_identities_fail_closed(self):
        for bad in ("bad", "A" * 40, "", None):
            with self.subTest(bad=bad), self.assertRaises(preview.MergePreviewError):
                preview.inspect(self.fixture.path, bad, self.fixture.root, self.fixture.dev)
        with self.assertRaisesRegex(preview.MergePreviewError, "must differ"):
            preview.inspect(self.fixture.path, self.fixture.dev, self.fixture.root, self.fixture.dev)

    def test_local_replace_ref_cannot_forge_merge_ancestry_or_conflict(self):
        actual = self.fixture.inspect()
        refs_before = self.fixture.git("show-ref")
        # A replacement aliases the main object but does not move main's ref.
        self.fixture.git("replace", self.fixture.main, self.fixture.root)
        refs_with_replace = self.fixture.git("show-ref")
        self.assertNotEqual(refs_before, refs_with_replace)
        result = self.fixture.inspect()
        self.assertEqual(actual, result)
        self.assertEqual(refs_with_replace, self.fixture.git("show-ref"))

    def test_cli_writes_new_report_once_and_never_overwrites(self):
        output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(output_dir.cleanup)
        target = Path(output_dir.name) / "safe-report.json"
        args = ["--repo", str(self.fixture.path), "--main-sha", self.fixture.main,
                "--root-pr-sha", self.fixture.root, "--development-sha", self.fixture.dev,
                "--output", str(target)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, preview.main(args))
        self.assertEqual(self.fixture.dev, json.loads(target.read_text())["source_dev"])
        first = target.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit) as blocked:
                preview.main(args)
        self.assertEqual(2, blocked.exception.code)
        self.assertIn("safe output unavailable", err.getvalue())
        self.assertEqual(first, target.read_bytes())


if __name__ == "__main__":
    unittest.main()
