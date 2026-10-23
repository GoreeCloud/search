"""Offline OS package observation and exact local candidate evidence checks."""

from copy import deepcopy
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime_os_inventory import (
    InventoryError, collect, parse_apk_installed, parse_dpkg_status, parse_os_release,
)
from verify_runtime_os_inventory import OSPackageEvidenceError, verify
from verify_runtime_python_inventory import verify as verify_python
import runtime_os_inventory


SHA = "a" * 40
IMAGE_ID = "sha256:" + "b" * 64
SOURCE = {"source_tree": "c" * 40, "input_sha256": {"requirements.txt": "d" * 64}}
IMAGE = {
    "schema": "goreecloud.search.local-image-candidate.v1",
    "repository": "https://github.com/GoreeCloud/search",
    "source_commit": SHA,
    "source_tree": SOURCE["source_tree"],
    "release_input_sha256": SOURCE["input_sha256"],
    "local_image_config_digest": IMAGE_ID,
    "image_tag": f"goreecloud/search:staging-{SHA[:12]}",
    "platform": "linux/amd64",
    "unsigned": True,
}
PYTHON = verify_python({
    "schema": "goreecloud.search.runtime-python-distributions.v1",
    "python_version": "3.12.7", "implementation": "CPython",
    "os": "linux", "machine": "x86_64",
    "distributions": [{"name": "granian", "version": "2.8.4"}],
}, IMAGE, SOURCE, SHA, IMAGE_ID)
OS = {
    "schema": "goreecloud.search.runtime-os-packages.v1",
    "os": "linux", "machine": "x86_64",
    "release": {"id": "alpine", "version_id": "3.21.3"},
    "package_manager": "apk",
    "packages": [
        {"name": "alpine-baselayout", "version": "3.7.0-r0", "arch": "x86_64"},
        {"name": "ca-certificates-bundle", "version": "20241010-r0", "arch": "noarch"},
    ],
}


class RuntimeOSInventoryTests(unittest.TestCase):
    def test_runner_reports_bounded_code_owned_reason_without_package_details(self):
        error_stream = StringIO()
        with patch.object(runtime_os_inventory, "collect", side_effect=InventoryError(
            "expected exactly one supported OS package database"
        )), redirect_stderr(error_stream):
            self.assertEqual(2, runtime_os_inventory.main())
        self.assertEqual("OS_PACKAGE_INVENTORY_BLOCKED: expected exactly one supported OS "
                         "package database\n", error_stream.getvalue())

    def test_realistic_alpine_package_database_is_sorted(self):
        raw = ("P:ca-certificates-bundle\nV:20241010-r0\nA:noarch\nT:certs\n\n"
               "P:alpine-baselayout\nV:3.7.0-r0\nA:x86_64\nC:checksum\n\n")
        self.assertEqual(OS["packages"], parse_apk_installed(raw))

    def test_realistic_debian_database_only_includes_installed(self):
        raw = ("Package: zlib1g\nStatus: install ok installed\nArchitecture: amd64\n"
               "Version: 1:1.3.dfsg-3\nDescription: libc library\n more text\n\n"
               "Package: old\nStatus: deinstall ok config-files\nArchitecture: all\nVersion: 0.1\n\n"
               "Package: base-files\nStatus: install ok installed\nArchitecture: amd64\n"
               "Version: 13.0+deb12u1\n")
        self.assertEqual([
            {"name": "base-files", "version": "13.0+deb12u1", "arch": "amd64"},
            {"name": "zlib1g", "version": "1:1.3.dfsg-3", "arch": "amd64"},
        ], parse_dpkg_status(raw))

    def test_valid_os_release_fields_never_emit_descriptive_or_private_metadata(self):
        raw = ('NAME="Alpine Linux"\nID=alpine\nVERSION_ID="3.21.3"\n'
               'PRETTY_NAME="Alpine Linux test image"\nHOME_URL="https://example.invalid"\n')
        self.assertEqual({"id": "alpine", "version_id": "3.21.3"}, parse_os_release(raw))

    def test_scanner_uses_only_fixed_package_db_paths_without_executing_package_manager(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "etc").mkdir()
            (root / "etc/os-release").write_text("ID=alpine\nVERSION_ID=3.21.3\n")
            (root / "lib/apk/db").mkdir(parents=True)
            (root / "lib/apk/db/installed").write_text(
                "P:alpine-baselayout\nV:3.7.0-r0\nA:x86_64\n")
            runtime = collect(root)
            self.assertEqual("apk", runtime["package_manager"])
            self.assertEqual("alpine-baselayout", runtime["packages"][0]["name"])

    def test_empty_ambiguous_duplicate_and_malformed_databases_block(self):
        invalid = (
            (parse_apk_installed, ""),
            (parse_apk_installed, "P:good\nV:1.0-r0\nA:x86_64\n\nP:good\nV:2.0-r0\nA:x86_64"),
            (parse_apk_installed, "P:good\nV:1.0-r0\n"),
            (parse_apk_installed, "P:bad name\nV:1.0-r0\nA:x86_64"),
            (parse_dpkg_status, "Package: good\nStatus: install ok installed\nVersion: 1.0"),
            (parse_dpkg_status, "Package: good\nPackage: forged\nStatus: install ok installed\nArchitecture: amd64\nVersion: 1"),
        )
        for parser, payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(InventoryError):
                parser(payload)

    def test_ambiguous_manager_presence_or_no_supported_db_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "etc").mkdir()
            (root / "etc/os-release").write_text("ID=alpine\nVERSION_ID=3.21.3\n")
            with self.assertRaises(InventoryError):
                collect(root)
            (root / "lib/apk/db").mkdir(parents=True)
            (root / "lib/apk/db/installed").write_text("P:good\nV:1-r0\nA:x86_64\n")
            (root / "var/lib/dpkg").mkdir(parents=True)
            (root / "var/lib/dpkg/status").write_text(
                "Package: good\nVersion: 1\nArchitecture: amd64\nStatus: install ok installed\n")
            with self.assertRaises(InventoryError):
                collect(root)

    def test_exact_source_image_python_chain_accepts_partial_unsigned_evidence(self):
        record = verify(deepcopy(OS), deepcopy(IMAGE), deepcopy(PYTHON), deepcopy(SOURCE), SHA, IMAGE_ID)
        self.assertEqual(2, record["package_count"])
        self.assertEqual(IMAGE_ID, record["local_image_config_digest"])
        self.assertEqual("apk", record["package_manager"])
        self.assertTrue(record["unsigned"])
        self.assertIn("manually_copied_or_unregistered_executables_and_shared_libraries",
                      record["not_evaluated"])

    def test_tampered_python_chain_fails_closed(self):
        for field, bad in (("source_commit", "e" * 40),
                           ("local_image_config_digest", "sha256:" + "f" * 64),
                           ("platform", "linux/arm64"), ("unsigned", False),
                           ("distribution_count", 0),
                           ("distribution_manifest_sha256", "0" * 64)):
            with self.subTest(field=field):
                python = deepcopy(PYTHON)
                python[field] = bad
                with self.assertRaises(OSPackageEvidenceError):
                    verify(OS, IMAGE, python, SOURCE, SHA, IMAGE_ID)

    def test_tampered_image_or_source_blocks(self):
        image = deepcopy(IMAGE)
        image["source_tree"] = "e" * 40
        with self.assertRaises(OSPackageEvidenceError):
            verify(OS, image, PYTHON, SOURCE, SHA, IMAGE_ID)
        changed = deepcopy(SOURCE)
        changed["input_sha256"]["requirements.txt"] = "e" * 64
        with self.assertRaises(OSPackageEvidenceError):
            verify(OS, IMAGE, PYTHON, changed, SHA, IMAGE_ID)

    def test_package_manager_architecture_and_schema_mismatch_blocks(self):
        for field, bad in (("package_manager", "rpm"), ("machine", "aarch64"),
                           ("os", "win32"), ("release", {"id": "alpine"}),
                           ("packages", OS["packages"] + [{"name": "secret", "version": "1", "arch": "s390x"}]),
                           ("unexpected", True)):
            with self.subTest(field=field):
                runtime = deepcopy(OS)
                runtime[field] = bad
                with self.assertRaises(OSPackageEvidenceError):
                    verify(runtime, IMAGE, PYTHON, SOURCE, SHA, IMAGE_ID)

    def test_unsorted_duplicate_and_extraneous_package_fields_block(self):
        for bad in (list(reversed(OS["packages"])),
                    OS["packages"] * 2,
                    [*OS["packages"], {"name": "token", "version": "1", "arch": "x86_64", "url": "secret"}]):
            with self.subTest(bad=bad):
                runtime = deepcopy(OS)
                runtime["packages"] = deepcopy(bad)
                with self.assertRaises(OSPackageEvidenceError):
                    verify(runtime, IMAGE, PYTHON, SOURCE, SHA, IMAGE_ID)


if __name__ == "__main__":
    unittest.main()
