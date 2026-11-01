# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fail-closed checks for the exact-candidate Linux runner boundary."""

from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

import native_candidate_runner_smoke as smoke
from scripts.build_native_linux_service import build_bundle


ROOT = Path(__file__).resolve().parents[2]
FAKE_SHA = 'a' * 40


class NativeCandidateSmokeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.archive = Path(temp.name) / 'candidate.pyz'
        self.archive.write_bytes(build_bundle(ROOT, FAKE_SHA))

    def test_mismatched_exact_source_fails_before_launch(self):
        with self.assertRaisesRegex(ValueError, 'exact checkout'):
            smoke.verify(self.archive, 'b' * 40)

    def test_extra_inherited_runtime_module_fails_before_launch(self):
        with ZipFile(self.archive, 'a', compression=ZIP_DEFLATED) as bundle:
            bundle.writestr('searx/__init__.py', b'not allowed')
        with self.assertRaisesRegex(ValueError, 'unexpected service files'):
            smoke.verify(self.archive, FAKE_SHA)

    def test_duplicate_archive_entry_fails_before_launch(self):
        with ZipFile(self.archive, 'a', compression=ZIP_DEFLATED) as bundle:
            bundle.writestr('native_search/index.py', b'bad duplicate')
        with self.assertRaisesRegex(ValueError, 'unexpected service files'):
            smoke.verify(self.archive, FAKE_SHA)

    def test_candidate_runs_disposable_approved_search_and_denies_browser_requests(self):
        smoke.verify(self.archive, FAKE_SHA)

    def test_ci_checks_out_exact_source_and_runs_the_uninstalled_candidate(self):
        workflow = (ROOT / '.github/workflows/native-search-development.yml').read_text()
        self.assertIn('ref: ${{ github.event.pull_request.head.sha || github.sha }}', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('python scripts/build_native_linux_service.py', workflow)
        self.assertIn('python tests/native/native_candidate_runner_smoke.py', workflow)
        self.assertIn('--expected-sha "$EXPECTED_SOURCE_SHA"', workflow)
        self.assertNotIn('docker push', workflow)
        self.assertNotIn('systemctl enable', workflow)


if __name__ == '__main__':
    unittest.main()
