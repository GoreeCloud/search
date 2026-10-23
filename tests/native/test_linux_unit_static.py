# SPDX-License-Identifier: AGPL-3.0-or-later
"""Check the owned Linux unit with disposable, uninstalled fixture paths.

This validates systemd's parser on a path-rebased copy of the actual unit, not
that systemd started it or enforced sandbox rules on a managed host.
"""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
UNIT = ROOT / 'deploy/native-linux/goreecloud-search-native.service'


class NativeLinuxUnitStaticTests(unittest.TestCase):
    def test_systemd_parses_the_actual_unit_with_disposable_provisioned_paths(self):
        analyzer = shutil.which('systemd-analyze')
        if analyzer is None:
            self.skipTest('systemd-analyze absent; requires separate Linux unit qualification')

        with tempfile.TemporaryDirectory(prefix='gc-search-native-unit-') as directory:
            fake_root = Path(directory)
            workdir = fake_root / 'var/lib/goreecloud-search-native'
            workdir.mkdir(parents=True)
            (workdir / 'index.db').write_bytes(b'synthetic placeholder; never a live index')
            bundle = fake_root / 'opt/goreecloud-search-native/search-native.pyz'
            bundle.parent.mkdir(parents=True)
            bundle.write_bytes(b'synthetic placeholder; never executed')
            unit_path = fake_root / 'goreecloud-search-native.service'
            unit_text = UNIT.read_text()
            unit_text = unit_text.replace(
                'WorkingDirectory=/var/lib/goreecloud-search-native',
                f'WorkingDirectory={workdir}')
            unit_text = unit_text.replace(
                'ConditionPathExists=/var/lib/goreecloud-search-native/index.db',
                f'ConditionPathExists={workdir / "index.db"}')
            unit_text = unit_text.replace(
                '/opt/goreecloud-search-native/search-native.pyz', str(bundle))
            unit_path.write_text(unit_text)

            check = subprocess.run([
                analyzer, 'verify', str(unit_path),
            ], capture_output=True, text=True, timeout=15, check=False)
            self.assertEqual(0, check.returncode, check.stderr)


if __name__ == '__main__':
    unittest.main()
