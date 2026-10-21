"""Synthetic non-mutating acceptance tests for new tested-source cutover."""
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from test_free_upgrade_preflight import m, entry, IMAGE_ID, PROFILE


ROUTE = m.WORKING_ROUTE
REV = '4d480b6dcdabbf4643a925644fb3f720a3fff277'
TAG = 'goreecloud/search:staging-4d480b6dcdab'
SITE = b'''unrelated.example {
    respond "ok"
}
search-dev.goreecloud.com {
    @netbird_client remote_ip 100.64.0.0/10
    handle @netbird_client {
        reverse_proxy goreecloud-search-free-upgrade-gateway:8080
    }
    respond "Forbidden" 403
}
'''
WORKING_PROFILE = PROFILE.replace(b'  private_search: true\n',
                                  b'  private_search: true\n  default_source_choice: working\n')


def build_fixture():
    old_project = ROUTE.old_search.removesuffix('-search-1')
    new_project = ROUTE.new_search.removesuffix('-search-1')
    containers = {
        ROUTE.old_search: entry(ROUTE.old_search, old_project,
                                {old_project+'_app_link',old_project+'_provider_egress'},
                                health='healthy'),
        ROUTE.old_ingress: entry(ROUTE.old_ingress,old_project,
                                 {old_project+'_app_link','proxy'}),
        ROUTE.new_search: entry(ROUTE.new_search,new_project,
                                {new_project+'_app_link',new_project+'_provider_egress'},
                                health='healthy',image=TAG),
        ROUTE.new_ingress: entry(ROUTE.new_ingress,new_project,
                                 {new_project+'_app_link','proxy'}),
    }
    containers[ROUTE.old_ingress]['NetworkSettings']['Networks']['proxy']['Aliases'] = [
        ROUTE.old.split(':')[0]]
    containers[ROUTE.new_ingress]['NetworkSettings']['Networks']['proxy']['Aliases'] = [
        ROUTE.new.split(':')[0]]
    image = {'Id': IMAGE_ID, 'Config': {
        'Labels': {'org.opencontainers.image.revision': REV}}}
    return containers, image


def evaluate(*, current=SITE, snapshot=SITE, profile=WORKING_PROFILE, containers=None):
    fixture, image = build_fixture()
    return m.evaluate(
        current, snapshot, 0o600, 0o600,
        fixture if containers is None else containers,
        image, TAG, REV,
        owner_current=1001, owner_snapshot=1001,
        profile_mounted=profile, profile_committed=WORKING_PROFILE,
        route=ROUTE,
    )


class WorkingReleaseGateTests(unittest.TestCase):
    def test_old_legacy_release_defaults_remain_available(self):
        self.assertEqual('goreecloud-search-free-canary-gateway:8080', m.LEGACY_ROUTE.old)
        self.assertEqual('goreecloud-search-free-upgrade-gateway:8080', ROUTE.old)
        self.assertEqual('goreecloud-search-free-working-gateway:8080', ROUTE.new)

    def test_valid_working_candidate_admitted_for_review_not_cutover(self):
        result=evaluate()
        self.assertEqual('admitted_for_manual_cutover_review',result['status'])
        self.assertEqual(result['passed'],result['total'])
        self.assertEqual(25,result['total'])

    def test_wrong_live_route_or_missing_rollback_blocks(self):
        bad=SITE.replace(ROUTE.old.encode(),ROUTE.new.encode())
        self.assertEqual('blocked_do_not_cutover',evaluate(current=bad)['status'])
        self.assertEqual('blocked_do_not_cutover',evaluate(snapshot=None)['status'])

    def test_no_default_choice_or_wrong_runtime_profile_blocks(self):
        self.assertEqual('blocked_do_not_cutover',evaluate(profile=PROFILE)['status'])
        wrong=WORKING_PROFILE.replace(b'default_source_choice: working',
                                      b'default_source_choice: all')
        self.assertEqual('blocked_do_not_cutover',evaluate(profile=wrong)['status'])

    def test_missing_new_gateway_and_wrong_docker_identity_blocks(self):
        containers,_=build_fixture()
        containers[ROUTE.new_ingress]['NetworkSettings']['Networks']['proxy']['Aliases']=[]
        self.assertEqual('blocked_do_not_cutover',evaluate(containers=containers)['status'])
        containers,_=build_fixture()
        containers[ROUTE.new_search]['Image']='sha256:'+'e'*64
        self.assertEqual('blocked_do_not_cutover',evaluate(containers=containers)['status'])

    def test_working_phase_cli_uses_distinct_containers_and_snapshot(self):
        containers,image=build_fixture()
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'Caddyfile'
            snapshot=Path(directory)/'snapshot'
            config.write_bytes(SITE);snapshot.write_bytes(SITE)
            config.chmod(0o600);snapshot.chmod(0o600)
            with patch.object(m,'inspect',side_effect=containers.get) as inspect, \
                 patch.object(m,'image_inspect',return_value=image), \
                 patch.object(m,'mounted_profile',return_value=WORKING_PROFILE), \
                 patch.object(m,'committed_profile',return_value=WORKING_PROFILE), \
                 patch('builtins.print') as output:
                rc=m.main(['--phase','working','--image',TAG,'--revision',REV,
                           '--caddyfile',str(config),'--snapshot',str(snapshot)])
                self.assertEqual(0,rc)
                self.assertEqual(set(containers),{call.args[0] for call in inspect.call_args_list})
                self.assertIn('admitted_for_manual_cutover_review',output.call_args.args[0])


if __name__=='__main__':
    unittest.main()
