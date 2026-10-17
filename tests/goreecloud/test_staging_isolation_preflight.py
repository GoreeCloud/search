"""Synthetic Docker-inspect fixtures for remote-only Search staging preflight."""
import copy
import contextlib
import io
import json
import sys
import unittest
from unittest.mock import patch, Mock

from utils.goreecloud_staging_isolation_check import (
    evaluate, main, STAGING_CONTAINER, STAGING_NETWORK,
)


def fixture():
    c = {
        "Name": "/" + STAGING_CONTAINER,
        "Config": {"User": "10001:10001", "Env": ["PRIVATE_FIXTURE_MARKER=never-log"]},
        "HostConfig": {
            "NetworkMode": STAGING_NETWORK, "Privileged": False,
            "ReadonlyRootfs": True, "CapAdd": [], "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"], "PidMode": "", "IpcMode": "private",
            "UsernsMode": "", "Binds": [], "Devices": [], "ExtraHosts": [],
            "PublishAllPorts": False, "PortBindings": {}, "Memory": 128 * 1024 * 1024,
            "PidsLimit": 32, "NanoCpus": 500_000_000, "AutoRemove": True,
        },
        "NetworkSettings": {"Networks": {STAGING_NETWORK: {}}, "Ports": {}},
        "Mounts": [],
    }
    n = {
        "Name": STAGING_NETWORK, "Driver": "bridge",
        "Labels": {"goreecloud.role": "search-staging-egress"}, "Internal": False,
    }
    return c, n


class IsolatedSearchStagingTests(unittest.TestCase):
    def test_hardened_nonpublic_staging_fixture_accepted_as_config_only(self):
        c, n = fixture()
        self.assertEqual([], evaluate(c, n))

    def test_dangerous_docker_runtime_controls_fail_preflight(self):
        mutations = (
            ("Config", "User", "0:0", "container_user_is_root"),
            ("HostConfig", "Privileged", True, "privileged_container"),
            ("HostConfig", "ReadonlyRootfs", False, "writable_root_filesystem"),
            ("HostConfig", "CapDrop", [], "capabilities_not_dropped"),
            ("HostConfig", "SecurityOpt", [], "new_privileges_not_blocked"),
            ("HostConfig", "NetworkMode", "host", "network_namespace_not_isolated"),
            ("HostConfig", "PidMode", "host", "shared_host_namespace"),
            ("HostConfig", "IpcMode", "host", "shared_host_namespace"),
            ("HostConfig", "UsernsMode", "host", "shared_host_namespace"),
            ("HostConfig", "Binds", ["/var/run/docker.sock:/docker.sock"], "unexpected_host_mounts_or_devices"),
            ("HostConfig", "ExtraHosts", ["host.docker.internal:host-gateway"], "host_resolution_override"),
            ("HostConfig", "PublishAllPorts", True, "public_or_bound_ports"),
            ("HostConfig", "PortBindings", {"80/tcp": [{"HostPort": "80"}]}, "public_or_bound_ports"),
            ("HostConfig", "Memory", 0, "memory_limit_missing_or_oversized"),
            ("HostConfig", "PidsLimit", 0, "pid_limit_missing_or_oversized"),
            ("HostConfig", "NanoCpus", 0, "cpu_limit_missing_or_oversized"),
            ("HostConfig", "AutoRemove", False, "ephemeral_teardown_not_enabled"),
        )
        for obj, key, value, expected in mutations:
            with self.subTest(key=key, value=str(value)):
                c, n = fixture()
                c[obj][key] = value
                self.assertIn(expected, evaluate(c, n))

    def test_network_and_mount_bypass_controls_fail_preflight(self):
        c, n = fixture()
        c['Name'] = '/caddy'
        self.assertIn('unexpected_container_identity', evaluate(c, n))
        c, n = fixture()
        c['Mounts'] = [{"Source": "/etc", "Destination": "/host"}]
        self.assertIn('unexpected_host_mounts_or_devices', evaluate(c, n))
        c, n = fixture()
        c['NetworkSettings']['Networks']['bridge'] = {}
        self.assertIn('network_namespace_not_isolated', evaluate(c, n))
        c, n = fixture()
        n['Labels'] = {}
        self.assertIn('staging_network_label_unverified', evaluate(c, n))

    def test_valid_inspection_never_claims_firewall_is_verified_or_prints_secrets(self):
        container, network = fixture()
        answers = [
            Mock(stdout=json.dumps([container])),
            Mock(stdout=json.dumps([network])),
        ]
        output = io.StringIO()
        with patch('utils.goreecloud_staging_isolation_check.subprocess.run', side_effect=answers):
            with patch.object(sys, 'argv', ['staging-check']):
                with contextlib.redirect_stdout(output):
                    with self.assertRaises(SystemExit) as code:
                        main()
        self.assertEqual(2, code.exception.code)
        self.assertIn('CONTAINER_CONFIG_PASS', output.getvalue())
        self.assertIn('NOT_QUALIFIED', output.getvalue())
        self.assertNotIn('never-log', output.getvalue())


if __name__ == '__main__':
    unittest.main()
