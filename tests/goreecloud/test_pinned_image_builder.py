"""Offline source/provenance contracts for a local-only pinned Search image build."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build_pinned_staging_image.sh"
DIST = ROOT / "container/dist.dockerfile"
BUILDER = ROOT / "container/builder.dockerfile"
BUILDER_IGNORE = ROOT / "container/builder.dockerfile.dockerignore"
ROOT_IGNORE = ROOT / ".dockerignore"


class PinnedImageBuildContracts(unittest.TestCase):
    def test_tracked_builder_is_directly_executable_without_running_docker(self):
        """The VPS uses the script as an entrypoint, not just via `bash`."""
        tracked = subprocess.run(
            ["git", "ls-files", "--stage", "--", "scripts/build_pinned_staging_image.sh"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=5,
        )
        self.assertEqual("100755", tracked.stdout.split()[0])
        # No arguments must stop at the usage gate, before image creation.
        result = subprocess.run(
            [str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(64, result.returncode)
        self.assertIn("40-character-commit-sha", result.stderr)
        self.assertEqual("", result.stdout)

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

    def test_builder_specific_context_excludes_only_generated_version_metadata(self):
        builder = BUILDER.read_text()
        specific = BUILDER_IGNORE.read_text().splitlines()
        root = ROOT_IGNORE.read_text().splitlines()
        self.assertIn('COPY ./searx/ ./searx/', builder)
        self.assertNotIn('COPY --exclude=', builder)
        self.assertEqual(
            [line for line in root if line and not line.startswith('#')],
            [line for line in specific if line and not line.startswith('#')][:-1],
        )
        self.assertEqual('searx/version_frozen.py', specific[-1])
        self.assertNotIn('searx/version_frozen.py', root)

    def test_builder_compression_checks_use_valid_find_exec_arguments(self):
        builder = BUILDER.read_text()
        self.assertNotIn('{}.gz +', builder)
        self.assertNotIn('{}.br +', builder)
        self.assertIn('-name "*.gz" -exec gzip --test {} +', builder)
        self.assertIn('-name "*.br" -exec brotli --test {} +', builder)


if __name__ == "__main__":
    unittest.main()
