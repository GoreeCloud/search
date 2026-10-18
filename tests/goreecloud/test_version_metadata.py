"""Git metadata must work with untracked development branches."""

import os
import subprocess
import unittest
from unittest.mock import patch

from searx import version


class VersionMetadataTests(unittest.TestCase):
    def test_current_local_branch_without_upstream(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(version, "subprocess_run", side_effect=[
                subprocess.CalledProcessError(128, "git rev-parse"),
                "stabilize/search-version-metadata-20261016",
                "https://github.com/GoreeCloud/search.git",
            ]) as run:
                self.assertEqual(version.get_git_url_and_branch(), (
                    "https://github.com/GoreeCloud/search",
                    "stabilize/search-version-metadata-20261016",
                ))
                self.assertEqual(run.call_args_list[1].args[0], "git branch --show-current")

    def test_detached_head_has_no_fabricated_branch(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(version, "subprocess_run", side_effect=[
                subprocess.CalledProcessError(128, "git rev-parse"),
                "",
                "https://github.com/GoreeCloud/search.git",
            ]):
                self.assertEqual(version.get_git_url_and_branch(), (
                    "https://github.com/GoreeCloud/search", "unknown",
                ))

    def test_tracked_remote_and_ssh_url(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(version, "subprocess_run", side_effect=[
                "origin/main", "git@github.com:GoreeCloud/search.git",
            ]) as run:
                self.assertEqual(version.get_git_url_and_branch(), (
                    "https://github.com/GoreeCloud/search", "main",
                ))
                self.assertEqual(run.call_count, 2)

    def test_only_trailing_git_suffix_is_removed(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(version, "subprocess_run", side_effect=[
                "origin/main", "https://code.git.example/repo.git",
            ]):
                self.assertEqual(version.get_git_url_and_branch(), (
                    "https://code.git.example/repo", "main",
                ))

    def test_github_actions_environment_avoids_git_calls(self):
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "GoreeCloud/search",
            "GITHUB_REF_NAME": "feature/update",
        }):
            with patch.object(version, "subprocess_run") as run:
                self.assertEqual(version.get_git_url_and_branch(), (
                    "https://github.com/GoreeCloud/search", "feature/update",
                ))
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
