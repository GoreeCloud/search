"""Bounded Docker log footprint for every free-search deployment variant.

Static guarantees only. A running container inherits its log options when it
is CREATED; editing Compose does not retroactively limit its existing logs.
"""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FILES = tuple(sorted((ROOT / 'deploy/vps').glob('compose.free-metasearch-*.yaml')))
EXPECTED_FILES = {
    'compose.free-metasearch-canary.yaml',
    'compose.free-metasearch-upgrade.yaml',
    'compose.free-metasearch-working.yaml',
    'compose.free-metasearch-staging.yaml',
}
SIZE_BYTES = 8 * 1024 * 1024
FILES_PER_CONTAINER = 3
MAX_BYTES_PER_CONTAINER = SIZE_BYTES * FILES_PER_CONTAINER


class FreeSearchLogRetentionContracts(unittest.TestCase):
    def test_covers_all_free_search_compose_variants(self):
        self.assertEqual(EXPECTED_FILES, {p.name for p in FILES})

    def test_search_and_ingress_are_both_bounded_and_reader_compatible(self):
        for file in FILES:
            with self.subTest(file=file.name):
                data = yaml.safe_load(file.read_text(encoding='utf-8'))
                services = data['services']
                self.assertEqual({'search', 'ingress'}, set(services))
                for name, service in services.items():
                    with self.subTest(container=name):
                        self.assertEqual({
                            'driver': 'json-file',
                            'options': {'max-size': '8m', 'max-file': '3'},
                        }, service['logging'])
                        self.assertLessEqual(SIZE_BYTES * int(
                            service['logging']['options']['max-file']),
                            MAX_BYTES_PER_CONTAINER)
                        self.assertTrue(service['read_only'])
                        self.assertNotIn('ports', service)
                        self.assertIn('ALL', service['cap_drop'])
                        self.assertIn('no-new-privileges:true', service['security_opt'])

    def test_each_project_has_48_mib_nominal_ceiling_for_container_logs(self):
        for file in FILES:
            data = yaml.safe_load(file.read_text())
            total = sum(
                SIZE_BYTES * int(service['logging']['options']['max-file'])
                for service in data['services'].values()
            )
            self.assertEqual(48 * 1024 * 1024, total)


if __name__ == '__main__':
    unittest.main()
