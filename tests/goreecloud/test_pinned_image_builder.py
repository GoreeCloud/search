"""Offline source/provenance contracts for a local-only pinned Search image build."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build_pinned_staging_image.sh"
DIST = ROOT / "container/dist.dockerfile"


class PinnedImageBuildContracts(unittest.TestCase):
    def test_bad_arguments_refused_before_build(self):
        result = subprocess.run(
            ["bash", str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, timeout=5
        )
        self.assertEqual(64, result.returncode)
        self.assertNotIn("docker build", result.stdout)
        self.assertIn("40-character-commit-sha", result.stderr)

    def test_wrong_commit_refused_before_build(self):
        result = subprocess.run(
            ["bash", str(SCRIPT), "0" * 40],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(65, result.returncode)
        self.assertIn("checkout revision differs", result.stderr)

    def test_builder_source_and_image_are_revision_scoped(self):
        src = SCRIPT.read_text()
        dist = DIST.read_text()
        self.assertIn('git status --porcelain --untracked-files=normal', src)
        self.assertIn('https://github.com/GoreeCloud/search.git', src)
        self.assertIn('python3 searx/version.py freeze', src)
        self.assertIn('PINNED_FROZEN_VERSION_PASS', src)
        self.assertLess(src.index('python3 searx/version.py freeze'), src.index('docker build'))
        self.assertIn('goreecloud/search-builder:staging-', src)
        self.assertIn('goreecloud/search:staging-', src)
        self.assertIn('--build-arg BUILDER_IMAGE="$BUILDER_IMAGE"', src)
        self.assertIn('--build-arg VCS_REVISION="$SOURCE_SHA"', src)
        self.assertIn('"org.opencontainers.image.revision"', src)
        self.assertIn('"org.opencontainers.image.source"', src)
        self.assertIn('ARG BUILDER_IMAGE=localhost/searxng/searxng:builder', dist)
        self.assertIn('FROM ${BUILDER_IMAGE} AS builder', dist)
        for unsafe in ("docker push", "docker compose up", "docker run", "git push"):
            self.assertNotIn(unsafe, src)

    def test_documented_build_requires_frozen_version(self):
        guide = (ROOT / "deploy/vps/README.md").read_text()
        self.assertIn('bash scripts/build_pinned_staging_image.sh "$SOURCE_SHA"', guide)
        self.assertIn('python3 searx/version.py freeze', guide)
        self.assertIn('test -f searx/version_frozen.py', guide)


if __name__ == "__main__":
    unittest.main()
