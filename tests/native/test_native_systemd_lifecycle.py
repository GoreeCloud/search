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
    UNIT_SOURCE,
    _stage,
    _require_ephemeral_host,
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


if __name__ == "__main__":
    unittest.main()
