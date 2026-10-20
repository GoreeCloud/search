"""Offline negative tests: never cut over with missing or mismatched release gates."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[2] / "scripts" / "free_upgrade_preflight.py"
spec = importlib.util.spec_from_file_location("free_upgrade_preflight", MODULE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

REV = "64c4cab8e2bdf538d718a8409e51ee76613133c0"
TAG = "goreecloud/search:staging-64c4cab8e2bd"
SITE = b'''other.domain.example {
    respond "ok"
}
search-dev.goreecloud.com {
    @netbird_client remote_ip 100.64.0.0/10
    handle @netbird_client {
        reverse_proxy goreecloud-search-free-canary-gateway:8080
    }
    handle {
        respond "Forbidden" 403
    }
}
'''
PROJECT_NEW = "goreecloud-search-free-upgrade"
PROJECT_OLD = "goreecloud-search-free-canary"
IMAGE_ID = "sha256:" + "a" * 64


def entry(name, project, networks, *, health=None, image=None):
    state = {"Status": "running"}
    if health:
        state["Health"] = {"Status": health}
    data = {
        "State": state,
        "Image": IMAGE_ID,
        "Config": {"Image": image or "goreecloud/caddy:2.11.4-porkbun-v0.3.1",
                   "Labels": {"com.docker.compose.project": project},
                   "Env": ["GRANIAN_WORKERS=1"]},
        "HostConfig": {"ReadonlyRootfs": True, "PortBindings": None},
        "NetworkSettings": {"Networks": {n: {"Aliases": []} for n in networks}},
    }
    if "ingress" in name:
        alias = (m.NEW if project == PROJECT_NEW else m.OLD).split(":")[0]
        data["NetworkSettings"]["Networks"]["proxy"]["Aliases"] = [alias]
    return data


def fixture():
    containers = {
        m.OLD_SEARCH: entry(m.OLD_SEARCH, PROJECT_OLD,
                            {PROJECT_OLD + "_app_link", PROJECT_OLD + "_provider_egress"},
                            health="healthy"),
        m.OLD_INGRESS: entry(m.OLD_INGRESS, PROJECT_OLD,
                             {PROJECT_OLD + "_app_link", "proxy"}),
        m.NEW_SEARCH: entry(m.NEW_SEARCH, PROJECT_NEW,
                            {PROJECT_NEW + "_app_link", PROJECT_NEW + "_provider_egress"},
                            health="healthy", image=TAG),
        m.NEW_INGRESS: entry(m.NEW_INGRESS, PROJECT_NEW,
                             {PROJECT_NEW + "_app_link", "proxy"}),
    }
    image = {"Id": IMAGE_ID, "Config": {"Labels": {"org.opencontainers.image.revision": REV}}}
    return containers, image


def evaluate(source=SITE, snapshot=SITE, mode=0o600, backmode=0o600,
             containers=None, image=None, owner=1001, snapshot_owner=1001):
    a, b = fixture()
    return m.evaluate(source, snapshot, mode, backmode,
                      a if containers is None else containers,
                      b if image is None else image, TAG, REV,
                      owner_current=owner, owner_snapshot=snapshot_owner)


class ReadonlyUpgradeAdmissionTests(unittest.TestCase):
    def test_valid_synthetic_parallel_state_is_admitted_for_review_not_reloaded(self):
        result = evaluate()
        self.assertEqual("admitted_for_manual_cutover_review", result["status"])
        self.assertEqual(result["passed"], result["total"])
        self.assertGreaterEqual(result["total"], 18)

    def test_missing_candidate_blocks_without_fake_green(self):
        a, _ = fixture()
        del a[m.NEW_SEARCH]
        self.assertEqual("blocked_do_not_cutover", evaluate(containers=a)["status"])

    def test_unhealthy_candidate_blocks(self):
        a, _ = fixture()
        a[m.NEW_SEARCH]["State"]["Health"]["Status"] = "starting"
        self.assertEqual("blocked_do_not_cutover", evaluate(containers=a)["status"])

    def test_gateway_collision_blocks(self):
        a, _ = fixture()
        a[m.NEW_INGRESS]["NetworkSettings"]["Networks"]["proxy"]["Aliases"] = [m.OLD.split(":")[0]]
        self.assertEqual("blocked_do_not_cutover", evaluate(containers=a)["status"])

    def test_unexpected_network_or_public_ports_blocks(self):
        a, _ = fixture()
        a[m.NEW_SEARCH]["NetworkSettings"]["Networks"]["proxy"] = {"Aliases": []}
        a[m.NEW_SEARCH]["HostConfig"]["PortBindings"] = {"8080/tcp": [{"HostPort": "8080"}]}
        self.assertEqual("blocked_do_not_cutover", evaluate(containers=a)["status"])

    def test_mismatched_image_revision_blocks(self):
        _, image = fixture()
        image["Config"]["Labels"]["org.opencontainers.image.revision"] = "0" * 40
        self.assertEqual("blocked_do_not_cutover", evaluate(image=image)["status"])

    def test_mutated_image_tag_does_not_override_running_image_id(self):
        containers, image = fixture()
        containers[m.NEW_SEARCH]["Image"] = "sha256:" + "b" * 64
        result = evaluate(containers=containers, image=image)
        self.assertEqual("blocked_do_not_cutover", result["status"])
        self.assertFalse(next(x["passed"] for x in result["checks"]
                              if x["check"] == "running_image_id_matches_local_image"))

    def test_missing_runtime_digest_blocks_even_if_tag_and_revision_match(self):
        containers, image = fixture()
        containers[m.NEW_SEARCH].pop("Image")
        self.assertEqual("blocked_do_not_cutover",evaluate(containers=containers,image=image)["status"])
        image.pop("Id")
        self.assertEqual("blocked_do_not_cutover",evaluate(image=image)["status"])

    def test_rollback_snapshot_owner_must_match_current(self):
        self.assertEqual("blocked_do_not_cutover",evaluate(snapshot_owner=0)["status"])
        self.assertEqual("blocked_do_not_cutover",evaluate(owner=None)["status"])

    def test_label_and_image_tag_must_refer_to_the_same_revision(self):
        containers, image = fixture()
        wrong_tag = "goreecloud/search:staging-" + "0" * 12
        containers[m.NEW_SEARCH]["Config"]["Image"] = wrong_tag
        result = m.evaluate(SITE, SITE, 0o600, 0o600,
                            containers, image, wrong_tag, REV,
                            owner_current=1001, owner_snapshot=1001)
        self.assertEqual("blocked_do_not_cutover",result["status"])

    def test_network_published_port_blocks_even_without_hostconfig_bindings(self):
        containers, image = fixture()
        containers[m.NEW_INGRESS]["NetworkSettings"]["Ports"] = {
            "8080/tcp": [{"HostIp":"0.0.0.0","HostPort":"8099"}]
        }
        self.assertEqual("blocked_do_not_cutover",evaluate(containers=containers,image=image)["status"])

    def test_live_route_already_changed_blocks_old_route_gate(self):
        changed = SITE.replace(m.OLD.encode(), m.NEW.encode())
        self.assertEqual("blocked_do_not_cutover", evaluate(source=changed, snapshot=changed)["status"])

    def test_wrong_netbird_acl_blocks(self):
        changed = SITE.replace(b"100.64.0.0/10", b"0.0.0.0/0")
        self.assertEqual("blocked_do_not_cutover", evaluate(source=changed, snapshot=changed)["status"])

    def test_unprotected_or_stale_backup_blocks(self):
        self.assertEqual("blocked_do_not_cutover", evaluate(backmode=0o644)["status"])
        self.assertEqual("blocked_do_not_cutover", evaluate(snapshot=SITE+b"# drift")["status"])
        self.assertEqual("blocked_do_not_cutover", evaluate(snapshot=None)["status"])

    def test_duplicate_search_site_or_wrong_current_mode_blocks(self):
        self.assertEqual("blocked_do_not_cutover", evaluate(source=SITE+SITE)["status"])
        self.assertEqual("blocked_do_not_cutover", evaluate(mode=0o644)["status"])

    def test_inspection_commands_are_strictly_read_only(self):
        class Fake:
            returncode = 0
            stdout = '[{"State":{"Status":"running"}}]'
        with patch.object(m.subprocess, "run", return_value=Fake()) as run:
            m.inspect("synthetic")
            m.image_inspect(TAG)
        self.assertEqual(["docker", "inspect", "--type", "container", "synthetic"],
                         run.call_args_list[0].args[0])
        self.assertEqual(["docker", "image", "inspect", TAG], run.call_args_list[1].args[0])

    def test_only_expected_staging_image_and_sha_are_accepted(self):
        self.assertTrue(m.IMAGE.fullmatch(TAG))
        self.assertTrue(m.SHA.fullmatch(REV))
        for bad in ("http://example.org/a", "goreecloud/search:latest", "goreecloud/search:staging-xxxxxxxxxxxx"):
            self.assertIsNone(m.IMAGE.fullmatch(bad))
        self.assertIsNone(m.SHA.fullmatch("not-a-commit"))

if __name__ == "__main__":
    unittest.main()
