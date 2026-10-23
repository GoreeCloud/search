"""Offline source/provenance contracts for a local-only pinned Search image build."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
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
        builder = BUILDER.read_text()
        self.assertIn('git status --porcelain --untracked-files=normal', src)
        self.assertIn('https://github.com/GoreeCloud/search.git', src)
        self.assertIn('python3 searx/version.py freeze', src)
        self.assertIn('PINNED_FROZEN_VERSION_PASS', src)
        self.assertLess(src.index('python3 searx/version.py freeze'), src.index('docker build'))
        self.assertIn('goreecloud/search-builder:staging-', src)
        self.assertIn('goreecloud/search:staging-', src)
        self.assertIn('--build-arg BUILDER_IMAGE="$BUILDER_IMAGE"', src)
        self.assertIn('--build-arg BUILDER_BASE_IMAGE="$BUILDER_BASE_REF"', src)
        self.assertIn('--build-arg RUNTIME_BASE_IMAGE="$RUNTIME_BASE_REF"', src)
        self.assertIn('--build-arg REQUESTED_BUILDER_BASE_REF="$BUILDER_BASE_REF"', src)
        self.assertIn('--build-arg REQUESTED_RUNTIME_BASE_REF="$RUNTIME_BASE_REF"', src)
        self.assertIn('IMAGE_REQUESTED_BUILDER_REF=', src)
        self.assertIn('IMAGE_REQUESTED_RUNTIME_REF=', src)
        self.assertIn('ARG BUILDER_BASE_IMAGE=docker.io/searxng/base:searxng-builder', builder)
        self.assertIn('FROM ${BUILDER_BASE_IMAGE} AS builder', builder)
        self.assertIn('ARG RUNTIME_BASE_IMAGE=docker.io/searxng/base:searxng', dist)
        self.assertIn('FROM ${RUNTIME_BASE_IMAGE} AS dist', dist)
        self.assertIn('org.goreecloud.search.requested-builder-base-ref="$REQUESTED_BUILDER_BASE_REF"', dist)
        self.assertIn('org.goreecloud.search.requested-runtime-base-ref="$REQUESTED_RUNTIME_BASE_REF"', dist)
        self.assertIn('--build-arg VCS_REVISION="$SOURCE_SHA"', src)
        self.assertIn('"org.opencontainers.image.revision"', src)
        self.assertIn('"org.opencontainers.image.source"', src)
        self.assertIn('ARG BUILDER_IMAGE=localhost/searxng/searxng:builder', dist)
        self.assertIn('FROM ${BUILDER_IMAGE} AS builder', dist)
        for unsafe in ("docker push", "docker compose up", "docker run", "git push"):
            self.assertNotIn(unsafe, src)

    def test_base_pin_opt_in_requires_both_canonical_immutable_references(self):
        """Fail before source inspection or Docker for partial/malformed pins."""
        digest = 'docker.io/searxng/base@sha256:' + 'a' * 64
        invalid_pairs = (
            {"GC_SEARCH_BUILDER_BASE_REF": digest},
            {"GC_SEARCH_RUNTIME_BASE_REF": digest},
            {"GC_SEARCH_BUILDER_BASE_REF": "", "GC_SEARCH_RUNTIME_BASE_REF": digest},
            {"GC_SEARCH_BUILDER_BASE_REF": digest, "GC_SEARCH_RUNTIME_BASE_REF": "docker.io/searxng/base:searxng"},
            {"GC_SEARCH_BUILDER_BASE_REF": digest, "GC_SEARCH_RUNTIME_BASE_REF": "docker.io/other/base@sha256:" + 'a' * 64},
            {"GC_SEARCH_BUILDER_BASE_REF": digest.upper(), "GC_SEARCH_RUNTIME_BASE_REF": digest},
            {"GC_SEARCH_BUILDER_BASE_REF": digest, "GC_SEARCH_RUNTIME_BASE_REF": digest[:-1]},
        )
        for extra in invalid_pairs:
            with self.subTest(extra=extra):
                env = {k: v for k, v in os.environ.items()
                       if k not in ('GC_SEARCH_BUILDER_BASE_REF', 'GC_SEARCH_RUNTIME_BASE_REF')}
                result = subprocess.run(
                    ["bash", str(SCRIPT), '0' * 40], cwd=ROOT, env={**env, **extra},
                    capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(64, result.returncode)
                self.assertIn('supply BOTH upstream base refs', result.stderr)
                self.assertNotIn('PINNED_FROZEN_VERSION_PASS', result.stdout)
        env = {k: v for k, v in os.environ.items()
               if k not in ('GC_SEARCH_BUILDER_BASE_REF', 'GC_SEARCH_RUNTIME_BASE_REF')}
        result = subprocess.run(
            ["bash", str(SCRIPT), '0' * 40], cwd=ROOT,
            env={**env, 'GC_SEARCH_BUILDER_BASE_REF': digest,
                 'GC_SEARCH_RUNTIME_BASE_REF': 'docker.io/searxng/base@sha256:' + 'b' * 64},
            capture_output=True, text=True, timeout=5,
        )
        # Valid syntax proceeds to the independent exact-source SHA gate.
        self.assertEqual(65, result.returncode)
        self.assertIn('checkout revision differs', result.stderr)

    def test_shell_build_entrypoint_parses(self):
        subprocess.run(['bash', '-n', str(SCRIPT)], check=True, timeout=5)

    def test_synthetic_build_routes_both_pins_and_fails_on_tampered_label(self):
        """Exercise the clean-source build contract with a fake Docker CLI only."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as log_tmp:
            root = Path(tmp)
            (root / 'scripts').mkdir()
            (root / 'searx').mkdir()
            (root / 'bin').mkdir()
            shutil.copyfile(SCRIPT, root / 'scripts/build_pinned_staging_image.sh')
            (root / '.gitignore').write_text('searx/version_frozen.py\n')
            (root / 'searx/version.py').write_text(textwrap.dedent('''\
                from pathlib import Path
                import subprocess
                short = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], text=True).strip()
                Path('searx/version_frozen.py').write_text(
                    "GIT_URL = 'https://github.com/GoreeCloud/search'\\n"
                    + "VERSION_STRING = 'synthetic+" + short + "'\\n")
            '''))
            mock = root / 'bin/docker'
            mock.write_text(textwrap.dedent('''\
                #!/usr/bin/env python3
                import json
                import os
                from pathlib import Path
                import sys
                args = sys.argv[1:]
                if args[0] == 'build':
                    with Path(os.environ['MOCK_DOCKER_LOG']).open('a') as output:
                        output.write(json.dumps(args) + '\\n')
                elif args[:2] == ['image', 'inspect']:
                    field = args[3]
                    if 'org.opencontainers.image.revision' in field:
                        print(os.environ['MOCK_SHA'])
                    elif 'org.opencontainers.image.source' in field:
                        print('https://github.com/GoreeCloud/search')
                    elif 'requested-builder-base-ref' in field:
                        print(os.environ['GC_SEARCH_BUILDER_BASE_REF'])
                    elif 'requested-runtime-base-ref' in field:
                        print('wrong' if os.environ.get('MOCK_TAMPER') else
                              os.environ['GC_SEARCH_RUNTIME_BASE_REF'])
                    elif field == '{{.Id}}':
                        print('sha256:' + 'e' * 64)
                    else:
                        sys.exit(1)
                else:
                    sys.exit(1)
            '''))
            mock.chmod(0o755)
            for args in (('init', '-q'), ('remote', 'add', 'origin',
                         'https://github.com/GoreeCloud/search.git'),
                         ('add', '.'), ('-c', 'user.name=Fixture',
                          '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')):
                subprocess.run(['git', *args], cwd=root, check=True,
                               capture_output=True, timeout=5)
            sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                          cwd=root, text=True, timeout=5).strip()
            builder_ref = 'docker.io/searxng/base@sha256:' + 'a' * 64
            runtime_ref = 'docker.io/searxng/base@sha256:' + 'b' * 64
            log = Path(log_tmp) / 'builds.jsonl'
            env = {**os.environ, 'PATH': str(root / 'bin') + os.pathsep + os.environ['PATH'],
                   'GC_SEARCH_BUILDER_BASE_REF': builder_ref,
                   'GC_SEARCH_RUNTIME_BASE_REF': runtime_ref,
                   'MOCK_SHA': sha, 'MOCK_DOCKER_LOG': str(log)}
            command = ['bash', 'scripts/build_pinned_staging_image.sh', sha]
            result = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                    text=True, timeout=10)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('BASE_IMAGE_REFERENCE_MODE=DIGEST_SYNTAX_ONLY_UNVERIFIED', result.stdout)
            import json
            builds = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(2, len(builds))
            self.assertIn('BUILDER_BASE_IMAGE=' + builder_ref, builds[0])
            self.assertIn('RUNTIME_BASE_IMAGE=' + runtime_ref, builds[1])
            self.assertIn('REQUESTED_BUILDER_BASE_REF=' + builder_ref, builds[1])
            self.assertIn('REQUESTED_RUNTIME_BASE_REF=' + runtime_ref, builds[1])
            tampered = subprocess.run(command, cwd=root, env={**env, 'MOCK_TAMPER': '1'},
                                      capture_output=True, text=True, timeout=10)
            self.assertEqual(66, tampered.returncode)
            self.assertIn('requested upstream base labels differ', tampered.stderr)

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
