"""Static checks for Development workflow triggers and OCI source provenance.

No Docker daemon, network access, or production environment is required.
"""
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
BRANCHES = (
    'main', 'feature/**', 'feat/**', 'fix/**', 'security/**',
    'stabilize/**', 'deploy/**', 'design/**', 'test/**', 'ci/**',
)
WORKFLOWS = (
    '.github/workflows/search-foundation.yml',
    '.github/workflows/native-search-development.yml',
)


class SourceProvenanceContracts(unittest.TestCase):
    def test_foundation_and_native_workflows_cover_same_active_branches(self):
        for path in WORKFLOWS:
            with self.subTest(path=path):
                data = yaml.load((ROOT / path).read_text(), Loader=yaml.BaseLoader)
                self.assertIn('pull_request', data['on'])
                self.assertEqual(list(BRANCHES), data['on']['push']['branches'])
                self.assertEqual('read', data['permissions']['contents'])

    def test_disposable_isolation_gate_runs_on_both_push_and_pr(self):
        workflow = yaml.load(
            (ROOT / '.github/workflows/search-foundation.yml').read_text(),
            Loader=yaml.BaseLoader,
        )
        self.assertIn('pull_request', workflow['on'])
        self.assertIn('push', workflow['on'])
        job = workflow['jobs']['disposable-egress-topology']
        self.assertEqual('ubuntu-latest', job['runs-on'])
        self.assertEqual('read', job['permissions']['contents'])
        commands = [step.get('run', '') for step in job['steps']]
        self.assertIn('python tests/goreecloud/ci_ephemeral_staging_topology.py', commands)
        source = (ROOT / 'tests/goreecloud/ci_ephemeral_staging_topology.py').read_text()
        self.assertIn('GATEWAY_EGRESS_LOSS_FAIL_CLOSED_PASS', source)
        self.assertIn('SYNTHETIC_GATEWAY_RECOVERY_PASS', source)
        self.assertIn('EPHEMERAL_NETWORK_TOPOLOGY_PASS', source)
        self.assertIn('"--internal"', source)

    def test_release_source_inventory_pins_pr_head_not_synthetic_merge(self):
        workflow = yaml.load(
            (ROOT / '.github/workflows/search-foundation.yml').read_text(),
            Loader=yaml.BaseLoader,
        )
        job = workflow['jobs']['exact-source-baseline']
        self.assertEqual('read', job['permissions']['contents'])
        checkout, inventory, upload = job['steps']
        expected = '${{ github.event.pull_request.head.sha || github.sha }}'
        self.assertEqual(expected, checkout['with']['ref'])
        self.assertEqual('false', checkout['with']['persist-credentials'])
        self.assertEqual(expected, inventory['env']['EXPECTED_SOURCE_SHA'])
        self.assertIn('scripts/source_baseline_inventory.py', inventory['run'])
        self.assertIn('--expected-sha "$EXPECTED_SOURCE_SHA"', inventory['run'])
        self.assertIn('--output "$RUNNER_TEMP/search-source-baseline.json"',
                      inventory['run'])
        self.assertEqual('error', upload['with']['if-no-files-found'])
        self.assertEqual('30', upload['with']['retention-days'])

    def test_dist_image_has_explicit_commit_label_build_argument(self):
        content = (ROOT / 'container/dist.dockerfile').read_text()
        self.assertRegex(content, r'(?m)^ARG VCS_REVISION=')
        self.assertRegex(
            content,
            r'org[.]opencontainers[.]image[.]revision="\$VCS_REVISION"',
        )

    def test_deployment_guide_checks_clean_checkout_and_image_revision(self):
        guide = (ROOT / 'deploy/vps/README.md').read_text()
        for expected in (
            'git status --porcelain',
            'git rev-parse HEAD',
            '--build-arg VCS_REVISION="$SOURCE_SHA"',
            'org.opencontainers.image.revision',
            'test "$IMAGE_REVISION" = "$SOURCE_SHA"',
            'source-revision label establishes declared provenance',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, guide)

    def test_current_readme_distinguishes_free_development_and_anchor(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('**Development environment**', readme)
        self.assertIn('**Tested free sources**', readme)
        self.assertIn('providers can see the VPS public IP', readme)
        self.assertIn('not an accepted Seal or Anchor release', readme)
        self.assertNotIn('**All Sources** is the default', readme)
        self.assertNotIn('**Lifecycle:** Development only', readme)


if __name__ == '__main__':
    unittest.main()
