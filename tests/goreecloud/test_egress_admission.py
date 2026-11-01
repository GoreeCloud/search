"""Offline fixture regressions for the read-only Search/Tor admission check.

Never calls Docker, Tor, the network or Search providers.
"""
import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from utils import goreecloud_search_egress_admission as admission


def fixture(internal=False):
    tor_id = "a" * 64
    def host(network):
        return {
            "NetworkMode": network, "Privileged": False, "ReadonlyRootfs": True,
            "CapAdd": [], "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "PortBindings": {}, "PublishAllPorts": False,
            "PidMode": "", "IpcMode": "",
        }

    search = {
        "Name": "/" + admission.SEARCH_NAME,
        "Config": {"User": "977:977", "Env": ["SEARCH_SECRET=synthetic-do-not-print"]},
        "HostConfig": host("container:" + tor_id),
    }
    tor = {
        "Id": tor_id, "Name": "/" + admission.TOR_NAME,
        "Config": {"User": "debian-tor"},
        "HostConfig": host("proxy"),
        "NetworkSettings": {"Networks": {"proxy": {"IPAddress": "private"}}},
    }
    return search, tor, {"proxy": {"Name": "proxy", "Internal": internal}}


class SearchTorAdmissionTests(unittest.TestCase):
    def test_external_bridge_in_shared_namespace_is_rejected(self):
        self.assertIn("shared_namespace_has_external_route", admission.assess(*fixture()))

    def test_internal_bridge_still_cannot_claim_tor_egress_or_qualification(self):
        findings = admission.assess(*fixture(internal=True))
        self.assertIn("tor_outbound_route_unavailable", findings)
        self.assertIn("host_firewall_and_live_leak_tests_unverified", findings)

    def test_wrong_identity_or_namespace_is_rejected(self):
        search, tor, networks = fixture()
        search["Name"] = "/different-container"
        search["HostConfig"]["NetworkMode"] = "bridge"
        findings = admission.assess(search, tor, networks)
        self.assertIn("unexpected_search_container", findings)
        self.assertIn("search_tor_namespace_unverified", findings)

    def test_insecure_docker_flags_produce_bounded_findings(self):
        search, tor, networks = fixture()
        search["HostConfig"].update(
            Privileged=True, CapAdd=["NET_ADMIN"], PortBindings={"80/tcp": [{}]}
        )
        tor["HostConfig"].update(ReadonlyRootfs=False, SecurityOpt=[])
        findings = admission.assess(search, tor, networks)
        for value in (
            "search_privileged", "search_extra_capabilities",
            "search_host_ports_published", "tor_writable_root",
            "tor_new_privileges_permitted",
        ):
            with self.subTest(finding=value):
                self.assertIn(value, findings)

    def test_inspection_is_allowlisted_and_redacts_secrets(self):
        search, tor, networks = fixture()
        fake = [
            Mock(stdout=json.dumps([search])),
            Mock(stdout=json.dumps([tor])),
            Mock(stdout=json.dumps([networks["proxy"]])),
        ]
        out = io.StringIO()
        with patch.object(admission.subprocess, "run", side_effect=fake) as client:
            with contextlib.redirect_stdout(out):
                code = admission.main()
        self.assertEqual(2, code)
        self.assertIn("NOT_QUALIFIED", out.getvalue())
        self.assertNotIn("synthetic-do-not-print", out.getvalue())
        self.assertEqual([
            ["docker", "inspect", admission.SEARCH_NAME],
            ["docker", "inspect", admission.TOR_NAME],
            ["docker", "network", "inspect", "proxy"],
        ], [call.args[0] for call in client.call_args_list])

    def test_docker_errors_never_echo_secrets_or_inspection_output(self):
        out = io.StringIO()
        failure = subprocess.CalledProcessError(
            1, ["docker", "inspect"], stderr="SECRET=do-not-echo"
        )
        with patch.object(admission.subprocess, "run", side_effect=failure):
            with contextlib.redirect_stdout(out):
                code = admission.main()
        self.assertEqual(2, code)
        self.assertEqual(
            "NOT_QUALIFIED: docker_inspection_unavailable\n", out.getvalue()
        )


if __name__ == "__main__":
    unittest.main()
