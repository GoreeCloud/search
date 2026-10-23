# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline checks for the isolated, owned Linux service candidate artifact."""

import contextlib
import hashlib
import http.client
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from native_search.index import SearchIndex
from scripts import build_native_linux_service as bundle


ROOT = Path(__file__).resolve().parents[2]
FAKE_SHA = "a" * 40


class NativeLinuxServiceBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "repo"
        for name in bundle.SERVICE_FILES:
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def build(self):
        return bundle.build_bundle(self.source, FAKE_SHA)

    def test_deterministic_strict_membership_and_hashed_provenance(self):
        first = self.build()
        self.assertEqual(first, self.build())
        artifact = self.root / "native.pyz"
        artifact.write_bytes(first)
        with ZipFile(artifact) as zipped:
            expected_names = sorted((*bundle.SERVICE_FILES, "__main__.py", bundle.MANIFEST_NAME))
            self.assertEqual(expected_names, sorted(zipped.namelist()))
            self.assertFalse(any("searx" in name.lower() or "crawler" in name.lower()
                                 or "repo_corpus" in name for name in zipped.namelist()))
            self.assertTrue(all(zipped.getinfo(name).date_time[:3] == (1980, 1, 1)
                                for name in zipped.namelist()))
            manifest = json.loads(zipped.read(bundle.MANIFEST_NAME))
            self.assertEqual(FAKE_SHA, manifest["source_commit"])
            self.assertEqual("development_loopback_service_only", manifest["mode"])
            self.assertIn("seal_and_anchor_qualification", manifest["not_evaluated"])
            for name in bundle.SERVICE_FILES:
                self.assertEqual(hashlib.sha256((self.source / name).read_bytes()).hexdigest(),
                                 manifest["source_sha256"][name])

    def test_reject_missing_symlink_oversized_or_ambiguous_source(self):
        with self.assertRaisesRegex(bundle.BundleError, "exact 40-character"):
            bundle.build_bundle(self.source, "unverified")
        source = self.source / "native_search/api.py"
        source.unlink()
        with self.assertRaisesRegex(bundle.BundleError, "missing or symlinked"):
            self.build()
        source.symlink_to(ROOT / "native_search/api.py")
        with self.assertRaisesRegex(bundle.BundleError, "missing or symlinked"):
            self.build()
        source.unlink()
        source.write_bytes(b"x" * (bundle.MAX_SOURCE_BYTES + 1))
        with self.assertRaisesRegex(bundle.BundleError, "budget"):
            self.build()

    def test_bundled_own_service_responds_to_loopback_search_and_has_no_import_path_to_repo(self):
        archive = self.root / "native.pyz"
        archive.write_bytes(self.build())
        help_response = subprocess.run([sys.executable, str(archive), "--help"],
                                       cwd=self.root, capture_output=True, text=True,
                                       timeout=8, check=True)
        self.assertIn("--db", help_response.stdout)
        self.assertNotIn("--seed", help_response.stdout)
        missing_response = subprocess.run([sys.executable, str(archive), "--db", str(self.root / "missing.db")],
                                          cwd=self.root, capture_output=True, text=True, timeout=8)
        self.assertNotEqual(0, missing_response.returncode)
        self.assertFalse((self.root / "missing.db").exists())

        database = self.root / "approved.sqlite"
        with SearchIndex(database) as index:
            index.add(url="https://example.org/native", title="Owned Search service",
                      body="Approved local fixture for Search development")
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
        except PermissionError:
            self.skipTest("host sandbox prohibits loopback sockets; normal CI runs real API check")
        process = subprocess.Popen([sys.executable, str(archive), "--db", str(database),
                                    "--port", str(port)], cwd=self.root,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            response = None
            for _ in range(80):
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.3)
                    conn.request("POST", "/v1/search", body=json.dumps({"query": "Search"}),
                                 headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    data = json.loads(response.read())
                    conn.close()
                    break
                except (ConnectionError, OSError):
                    if process.poll() is not None:
                        break
                    time.sleep(0.05)
            self.assertIsNotNone(response, "candidate service failed to accept loopback requests")
            self.assertEqual(200, response.status)
            self.assertEqual("goreecloud-native-index", data["source"])
            self.assertEqual("https://example.org/native", data["results"][0]["url"])
        finally:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)

    def test_source_verified_cli_refuses_to_overwrite_an_artifact(self):
        target = self.root / "existing.pyz"
        target.write_bytes(b"important prior artifact")
        with patch.object(bundle, "collect", return_value={}),\
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as blocked:
                bundle.main(["--expected-sha", FAKE_SHA, "--output", str(target)])
        self.assertEqual(2, blocked.exception.code)
        self.assertEqual(b"important prior artifact", target.read_bytes())

    def test_cli_builds_new_archive_after_two_exact_source_checks(self):
        destination = self.root / "new-service.pyz"
        stdout = io.StringIO()
        with patch.object(bundle, "REPO", self.source),\
                patch.object(bundle, "collect", return_value={}) as check_source,\
                contextlib.redirect_stdout(stdout):
            self.assertEqual(0, bundle.main(["--expected-sha", FAKE_SHA,
                                             "--output", str(destination)]))
        self.assertEqual(2, check_source.call_count)
        self.assertEqual(self.build(), destination.read_bytes())
        output = json.loads(stdout.getvalue())
        self.assertEqual(hashlib.sha256(destination.read_bytes()).hexdigest(),
                         output["artifact_sha256"])
        self.assertEqual("candidate_only_not_install_or_anchor_evidence", output["status"])

    def test_systemd_template_is_disabled_by_default_and_denies_egress(self):
        unit = (ROOT / "deploy/native-linux/goreecloud-search-native.service").read_text()
        self.assertIn("IPAddressDeny=any", unit)
        self.assertIn("IPAddressAllow=localhost", unit)
        self.assertIn("NoNewPrivileges=yes", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("User=goreecloud-search", unit)
        self.assertIn("ConditionPathExists=", unit)
        self.assertNotIn("\n[Install]\n", unit)
        self.assertNotIn("crawler", unit.lower())
        self.assertNotIn("searxng", unit.lower())


if __name__ == "__main__":
    unittest.main()
