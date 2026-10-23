# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline invariants for the optional real ephemeral systemd acceptance.

The privileged host test is intentionally not run from local unittest:
GitHub-hosted Linux CI must actually boot the unit via the OS manager.
"""

from pathlib import Path
from unittest import mock
import os
import tempfile
import unittest

from native_systemd_lifecycle_smoke import (
    DIAGNOSTIC_STAGES,
    LifecycleBlocked,
    LifecycleWithTeardownFailure,
    UNIT_SOURCE,
    _stage,
    _require_ephemeral_host,
    _cleanup_created_unit,
    _teardown_preserving_primary,
    _validate_archive,
    blocked_message,
    render_temporary_unit,
)


class NativeSystemdLifecycleOfflineTests(unittest.TestCase):
    def setUp(self):
        self.template = UNIT_SOURCE.read_text(encoding="utf-8")
        self.directory = Path("/run/gc-search-native-ci-test")
        self.archive = self.directory / "search-native.pyz"
        self.database = self.directory / "index.db"

    def test_exact_existing_protected_unit_is_rebased_not_enabled(self):
        unit = render_temporary_unit(self.template, self.directory,
                                     self.archive, self.database, 38745)
        self.assertIn("User=nobody", unit)
        self.assertIn("Group=nogroup", unit)
        self.assertIn(f"WorkingDirectory={self.directory}", unit)
        self.assertIn(f"ConditionPathExists={self.database}", unit)
        self.assertIn(f"ReadWritePaths={self.directory}", unit)
        self.assertIn(f"ExecStart=/usr/bin/python3 -I -B {self.archive} "
                      f"--db {self.database} --port 38745", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("NoNewPrivileges=yes", unit)
        self.assertIn("IPAddressDeny=any", unit)
        self.assertIn("IPAddressAllow=localhost", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertNotIn("[Install]", [line.strip() for line in unit.splitlines()])
        self.assertNotIn("/var/lib/goreecloud-search-native", unit)
        self.assertNotIn("/opt/goreecloud-search-native", unit)

    def test_refuse_security_downgrade(self):
        cases = (
            self.template.replace("NoNewPrivileges=yes", "NoNewPrivileges=no"),
            self.template.replace("IPAddressDeny=any", "IPAddressDeny=none"),
            self.template.replace("Restart=on-failure", "Restart=no"),
            self.template + "\n[Install]\nWantedBy=multi-user.target\n",
            self.template + "\nProtectSystem=strict\n",
            self.template.replace("User=goreecloud-search", "User=root"),
            self.template.replace("ExecStart=/usr/bin/python3", "ExecStart=/usr/bin/env python3"),
        )
        for template in cases:
            with self.subTest(source=template[-70:]):
                with self.assertRaises(LifecycleBlocked):
                    render_temporary_unit(template, self.directory,
                                          self.archive, self.database, 38745)

    def test_refuse_invalid_port(self):
        for port in (0, -3, 65536):
            with self.subTest(port=port), self.assertRaises(LifecycleBlocked):
                render_temporary_unit(self.template, self.directory,
                                      self.archive, self.database, port)

    def test_privileged_smoke_refuses_non_ephemeral_environment(self):
        with mock.patch.dict(os.environ,
                             {"GITHUB_ACTIONS": "false", "RUNNER_ENVIRONMENT": "github-hosted"}), \
                self.assertRaises(LifecycleBlocked):
            _require_ephemeral_host()
        with mock.patch.dict(os.environ,
                             {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"}), \
                self.assertRaises(LifecycleBlocked):
            _require_ephemeral_host()

    def test_archive_identity_rejects_non_commit_and_wrong_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.pyz"
            candidate.write_bytes(b"not a zipapp")
            with self.assertRaises(LifecycleBlocked):
                _validate_archive(candidate, "a" * 40)
            with self.assertRaises(LifecycleBlocked):
                _validate_archive(candidate, "not-a-commit")

    def test_fixed_stage_diagnostic_excludes_arbitrary_exception_content(self):
        secret = "do-not-leak:/private/path?query=confidential"
        self.assertEqual("NATIVE_SYSTEMD_LIFECYCLE_BLOCKED stage=unknown: "
                         "no managed-service acceptance\n",
                         blocked_message(RuntimeError(secret)))
        for stage in DIAGNOSTIC_STAGES:
            with self.subTest(stage=stage):
                self.assertEqual(
                    f"NATIVE_SYSTEMD_LIFECYCLE_BLOCKED stage={stage}: "
                    "no managed-service acceptance\n",
                    blocked_message(LifecycleBlocked(stage)))
        self.assertNotIn(secret, blocked_message(LifecycleBlocked(secret)))

    def test_stage_context_discards_sensitive_os_and_management_errors(self):
        secret = "sensitive systemd output /mnt/internal/file"
        with self.assertRaises(LifecycleBlocked) as failure:
            with _stage("manager-reload"):
                raise OSError(secret)
        self.assertEqual("manager-reload", str(failure.exception))
        self.assertNotIn(secret, blocked_message(failure.exception))

    def test_stage_context_cannot_emit_new_unreviewed_categories(self):
        with self.assertRaises(AssertionError):
            with _stage("unexpected-checkout-path"):
                pass

    def test_unloaded_unit_is_removed_without_stop_request(self):
        # systemd-analyze can reject the file before daemon-reload. This
        # previously caused a spurious systemctl stop failure in finally.
        state = {
            "LoadState": "not-found", "ActiveState": "inactive",
            "MainPID": "0", "ControlPID": "0",
        }
        with tempfile.TemporaryDirectory() as tmp:
            unit_path = Path(tmp) / "goreecloud-native-ci-unique.service"
            unit_path.write_text("synthetic unit; never executed")
            with mock.patch("native_systemd_lifecycle_smoke._show",
                            side_effect=lambda unit, key: state[key]), \
                    mock.patch("native_systemd_lifecycle_smoke._run") as runner:
                _cleanup_created_unit("goreecloud-native-ci-unique.service", unit_path)
            self.assertFalse(unit_path.exists())
            runner.assert_called_once_with("systemctl", "daemon-reload")

    def test_loaded_process_is_stopped_and_accounted_for_before_unlink(self):
        state = {
            "LoadState": "loaded", "ActiveState": "active",
            "MainPID": "1234", "ControlPID": "0",
        }

        def simulate_manager(*args, **kwargs):
            if args == ("systemctl", "stop", "goreecloud-native-ci-unique.service"):
                state.update(ActiveState="inactive", MainPID="0")

        with tempfile.TemporaryDirectory() as tmp:
            unit_path = Path(tmp) / "goreecloud-native-ci-unique.service"
            unit_path.write_text("synthetic unit; never executed")
            with mock.patch("native_systemd_lifecycle_smoke._show",
                            side_effect=lambda unit, key: state[key]), \
                    mock.patch("native_systemd_lifecycle_smoke._run",
                               side_effect=simulate_manager) as runner:
                _cleanup_created_unit("goreecloud-native-ci-unique.service", unit_path)
            self.assertFalse(unit_path.exists())
            self.assertEqual(1, sum(call.args[:2] == ("systemctl", "stop")
                                    for call in runner.call_args_list))
            self.assertFalse(any(call.args[:2] == ("systemctl", "reset-failed")
                                 for call in runner.call_args_list))

    def test_unaccounted_process_prevents_unlink(self):
        state = {
            "LoadState": "loaded", "ActiveState": "active",
            "MainPID": "1234", "ControlPID": "0",
        }
        with tempfile.TemporaryDirectory() as tmp:
            unit_path = Path(tmp) / "goreecloud-native-ci-unique.service"
            unit_path.write_text("synthetic unit; never executed")
            with mock.patch("native_systemd_lifecycle_smoke._show",
                            side_effect=lambda unit, key: state[key]), \
                    mock.patch("native_systemd_lifecycle_smoke._run"):
                with self.assertRaises(LifecycleBlocked):
                    _cleanup_created_unit("goreecloud-native-ci-unique.service", unit_path)
            self.assertTrue(unit_path.exists())

    def test_primary_failure_survives_teardown_failure_without_leakage(self):
        secret = "private index /run/secret.sql query=forbidden"
        with mock.patch("native_systemd_lifecycle_smoke._cleanup_created_unit",
                        side_effect=OSError(secret)):
            with self.assertRaises(LifecycleWithTeardownFailure) as failure:
                try:
                    with _stage("unit-verify"):
                        raise OSError(secret)
                finally:
                    _teardown_preserving_primary("goreecloud-native-ci-unique.service",
                                                 Path("/run/systemd/system/unused-unit.service"))
        diagnostic = blocked_message(failure.exception)
        self.assertEqual(
            "NATIVE_SYSTEMD_LIFECYCLE_BLOCKED primary=unit-verify "
            "cleanup=teardown: no managed-service acceptance\n", diagnostic)
        self.assertNotIn(secret, diagnostic)

    def test_cleanup_only_failure_remains_single_stage(self):
        with mock.patch("native_systemd_lifecycle_smoke._cleanup_created_unit",
                        side_effect=OSError("private path")):
            with self.assertRaises(LifecycleBlocked) as failure:
                _teardown_preserving_primary("goreecloud-native-ci-unique.service",
                                             Path("/run/systemd/system/unused-unit.service"))
        self.assertEqual("NATIVE_SYSTEMD_LIFECYCLE_BLOCKED stage=teardown: "
                         "no managed-service acceptance\n",
                         blocked_message(failure.exception))

    def test_cleanup_reports_fixed_inspection_or_reload_stage_only(self):
        state = {
            "LoadState": "not-found", "ActiveState": "inactive",
            "MainPID": "0", "ControlPID": "0",
        }
        secret = "private-token:///run/owner-query"
        with tempfile.TemporaryDirectory() as tmp:
            unit_path = Path(tmp) / "goreecloud-native-ci-unique.service"
            unit_path.write_text("synthetic unit; never executed")
            with mock.patch("native_systemd_lifecycle_smoke._show",
                            side_effect=OSError(secret)):
                with self.assertRaises(LifecycleBlocked) as failure:
                    _cleanup_created_unit("goreecloud-native-ci-unique.service", unit_path)
            self.assertEqual("teardown-inspect", str(failure.exception))
            self.assertTrue(unit_path.exists())
            with mock.patch("native_systemd_lifecycle_smoke._show",
                            side_effect=lambda unit, key: state[key]), \
                    mock.patch("native_systemd_lifecycle_smoke._run",
                               side_effect=OSError(secret)):
                with self.assertRaises(LifecycleBlocked) as failure:
                    _cleanup_created_unit("goreecloud-native-ci-unique.service", unit_path)
            self.assertEqual("teardown-reload", str(failure.exception))
            self.assertFalse(unit_path.exists())
            self.assertNotIn(secret, blocked_message(failure.exception))


if __name__ == "__main__":
    unittest.main()
