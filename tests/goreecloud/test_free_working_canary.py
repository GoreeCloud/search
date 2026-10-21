"""Offline guarantees for the separate free-source Development cutover canary."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / 'deploy/vps/compose.free-metasearch-upgrade.yaml'
CANDIDATE = ROOT / 'deploy/vps/compose.free-metasearch-working.yaml'


class WorkingCanaryContracts(unittest.TestCase):
    def test_unique_project_and_route_alias(self):
        old = yaml.safe_load(CURRENT.read_text())
        new = yaml.safe_load(CANDIDATE.read_text())
        self.assertEqual('goreecloud-search-free-working', new['name'])
        self.assertNotEqual(old['name'], new['name'])
        old_aliases = old['services']['ingress']['networks']['private_ingress']['aliases']
        new_aliases = new['services']['ingress']['networks']['private_ingress']['aliases']
        self.assertEqual(['goreecloud-search-free-working-gateway'], new_aliases)
        self.assertFalse(set(old_aliases) & set(new_aliases))
        self.assertEqual({'search', 'ingress'}, set(new['services']))

    def test_nothing_published_and_data_stays_isolated(self):
        new = yaml.safe_load(CANDIDATE.read_text())
        services = new['services']
        self.assertEqual({'provider_egress', 'app_link'}, set(services['search']['networks']))
        self.assertEqual({'app_link', 'private_ingress'}, set(services['ingress']['networks']))
        self.assertEqual('proxy', new['networks']['private_ingress']['name'])
        self.assertTrue(new['networks']['private_ingress']['external'])
        self.assertTrue(new['networks']['app_link']['internal'])
        self.assertFalse(new['networks']['provider_egress']['internal'])
        for name, service in services.items():
            with self.subTest(name=name):
                self.assertNotIn('ports', service)
                self.assertTrue(service['read_only'])
                self.assertIn('ALL', service['cap_drop'])
                self.assertIn('no-new-privileges:true', service['security_opt'])
                self.assertEqual('unless-stopped', service['restart'])
        self.assertNotIn('search-cache', str(services))
        self.assertNotIn('private-settings.yml', str(services))

    def test_single_worker_bounded_profile_health_gated_start(self):
        new = yaml.safe_load(CANDIDATE.read_text())
        s = new['services']['search']
        self.assertEqual('1', s['environment']['GRANIAN_WORKERS'])
        self.assertTrue(any('settings.free-first.yml' in m for m in s['volumes']))
        self.assertTrue(any(m.endswith(':ro') for m in s['volumes']))
        self.assertIn('/readyz', ' '.join(s['healthcheck']['test']))
        self.assertEqual(
            {'search': {'condition': 'service_healthy'}},
            new['services']['ingress']['depends_on'],
        )
        free = yaml.safe_load((ROOT / 'configs/goreecloud/settings.free-first.yml').read_text())
        self.assertEqual('working', free['goreecloud']['default_source_choice'])
        self.assertEqual(12, free['goreecloud']['request_budget_per_minute'])
        self.assertFalse(free['goreecloud']['require_anonymous_egress'])
        self.assertEqual({}, free['outgoing']['proxies'])
        self.assertFalse(free['outgoing']['using_tor_proxy'])

if __name__ == '__main__':
    unittest.main()
