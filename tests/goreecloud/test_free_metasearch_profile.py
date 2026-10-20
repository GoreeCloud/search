"""Offline free-first direct metasearch profile and staging boundaries."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FREE = ROOT / 'configs/goreecloud/settings.free-first.yml'
PRIVATE = ROOT / 'configs/goreecloud/settings.yml'
STAGING = ROOT / 'deploy/vps/compose.free-metasearch-staging.yaml'
INDEX = ROOT / 'searx/templates/simple/index.html'
PRIVACY = ROOT / 'searx/static/themes/simple/goreecloud/privacy.html'

class FreeMetasearchProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load(FREE.read_text())
        cls.compose = yaml.safe_load(STAGING.read_text())
        cls.services = cls.compose['services']

    def test_separate_tor_profile_unchanged_and_direct_access_opt_in(self):
        tor = yaml.safe_load(PRIVATE.read_text())
        self.assertTrue(tor['goreecloud']['require_anonymous_egress'])
        self.assertTrue(tor['outgoing']['using_tor_proxy'])
        self.assertFalse(self.config['goreecloud']['require_anonymous_egress'])
        self.assertFalse(self.config['outgoing']['using_tor_proxy'])
        self.assertEqual({}, self.config['outgoing']['proxies'])

    def test_free_public_web_providers_without_paid_adapters(self):
        names = self.config['use_default_settings']['engines']['keep_only']
        for name in ('brave','startpage','qwant','duckduckgo','ecosia','bing','google'):
            self.assertIn(name,names)
        for paid in ('braveapi','exaapi'):
            self.assertNotIn(paid,names)
            self.assertFalse(any(engine.get('name')==paid for engine in self.config['engines']))
        self.assertIn('html',self.config['search']['formats'])
        self.assertTrue(self.config['server']['method']=='POST')
        self.assertFalse(self.config['server']['public_instance'])
        self.assertEqual('',self.config['search']['autocomplete'])

    def test_separate_project_and_two_containers_without_tor(self):
        self.assertEqual('goreecloud-search-free-staging',self.compose['name'])
        self.assertEqual({'search','ingress'},set(self.services))
        self.assertNotIn('tor',self.services)
        self.assertNotIn('relay',self.services)
        self.assertEqual({'provider_egress','app_link'},set(self.services['search']['networks']))
        self.assertEqual({'app_link','private_ingress'},set(self.services['ingress']['networks']))
        self.assertFalse(self.compose['networks']['provider_egress']['internal'])
        self.assertTrue(self.compose['networks']['app_link']['internal'])
        self.assertFalse(self.compose['networks']['provider_egress']['enable_ipv6'])
        self.assertEqual('SEARCH_FREE_INGRESS_NETWORK',self.compose['networks']['private_ingress']['name'].split(':')[0].removeprefix('${'))
        self.assertNotIn('proxy',self.services['ingress']['networks'])

    def test_no_public_ports_no_live_volumes_and_one_approved_upstream(self):
        for name,service in self.services.items():
            with self.subTest(name=name):
                self.assertNotIn('ports',service)
                self.assertTrue(service['read_only'])
                self.assertIn('ALL',service['cap_drop'])
                self.assertIn('no-new-privileges:true',service['security_opt'])
                self.assertEqual('no',str(service['restart']))
        self.assertIn('settings.free-first.yml',
                      str(self.services['search']['volumes']))
        self.assertNotIn('search-cache',str(self.services))
        self.assertEqual('goreecloud-search-free-staging-gateway',
                         self.services['ingress']['networks']['private_ingress']['aliases'][0])
        self.assertNotIn('goreecloud-search-gateway',
                         str(self.services['ingress']))

    def test_page_explains_server_ip_and_provider_query_disclosure(self):
        self.assertIn('direct HTTPS',INDEX.read_text())
        notice=PRIVACY.read_text()
        self.assertIn('search providers can see the server',notice)
        self.assertIn('public IP address',notice)
        self.assertIn('Neither profile grants paid API access',notice)

if __name__=='__main__':
    unittest.main()
