"""Offline, bounded selected ELF observations and exact evidence-chain tests."""

from copy import deepcopy
from contextlib import redirect_stderr
from io import StringIO
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import runtime_binary_hash_inventory as scanner
from verify_runtime_binary_hash_inventory import BinaryEvidenceError, verify
from verify_runtime_os_inventory import verify as verify_os
from verify_runtime_python_inventory import verify as verify_python


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
VOID = {
    "schema": "goreecloud.search.runtime-os-registry-unavailable.v1",
    "os": "linux", "machine": "x86_64",
    "release": {"id": "void", "version_id": None},
    "package_manager": "xbps", "package_inventory_status": "unavailable",
    "reason": "runtime_xbps_package_registry_removed",
}
OS_EVIDENCE = verify_os(VOID, IMAGE, PYTHON, SOURCE, SHA, IMAGE_ID)


class RuntimeSelectedELFTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "usr/bin"
        self.lib = self.root / "usr/lib"
        self.bin.mkdir(parents=True)
        self.lib.mkdir(parents=True)
        self.busybox = b"\x7fELF\x02core executable fixed bytes"
        self.libc = b"\x7fELF\x02shared library fixed bytes"
        (self.bin / "busybox").write_bytes(self.busybox)
        (self.lib / "libc.so.6").write_bytes(self.libc)

    def _runtime(self):
        with patch.object(scanner.platform, "machine", return_value="x86_64"):
            return scanner.collect(self.root)

    def _verify(self, runtime=None, *, image=IMAGE, python=PYTHON, os_evidence=OS_EVIDENCE,
                source=SOURCE, sha=SHA, image_id=IMAGE_ID):
        return verify(self._runtime() if runtime is None else runtime,
                      image, python, os_evidence, source, sha, image_id)

    def test_deterministic_selected_elf_hashes_are_byte_exact_and_limited(self):
        (self.bin / "python3").write_bytes(b"#!/usr/bin/python\n")  # Not ELF.
        (self.bin / "curl").write_bytes(b"\x7fELF\x02another file")
        (self.bin / "secret-tool").write_bytes(b"\x7fELF\x02not selected")
        (self.lib / "libsecret.so").write_bytes(b"#!/bin/sh\n")  # Linker script.
        (self.bin / "busybox-shadow").symlink_to("busybox")
        runtime = self._runtime()
        self.assertEqual(runtime, self._runtime())
        self.assertEqual(["/usr/bin/busybox", "/usr/bin/curl", "/usr/lib/libc.so.6"],
                         [row["path"] for row in runtime["files"]])
        self.assertEqual(hashlib.sha256(self.busybox).hexdigest(), runtime["files"][0]["sha256"])
        self.assertEqual(sum(row["size_bytes"] for row in runtime["files"]),
                         runtime["total_bytes_hashed"])

    def test_symlinked_selected_file_is_not_dereferenced(self):
        (self.bin / "python3").symlink_to("busybox")
        (self.lib / "libduplicate.so").symlink_to("libc.so.6")
        self.assertEqual(2, len(self._runtime()["files"]))

    def test_symlinked_system_directory_fails_closed(self):
        (self.root / "usr/lib").rename(self.root / "usr/lib-real")
        (self.root / "usr/lib").symlink_to("lib-real")
        with self.assertRaises(scanner.BinaryInventoryBlocked):
            self._runtime()

    def test_missing_or_non_elf_required_core_binary_fails_closed(self):
        (self.bin / "busybox").write_bytes(b"#! not ELF")
        with self.assertRaises(scanner.BinaryInventoryBlocked):
            self._runtime()

    def test_missing_direct_regular_library_fails_closed(self):
        (self.lib / "libc.so.6").unlink()
        (self.lib / "libc.so.6").symlink_to("/usr/lib/elsewhere")
        with self.assertRaises(scanner.BinaryInventoryBlocked):
            self._runtime()

    def test_per_file_cap_fails_without_large_real_allocation(self):
        with (self.lib / "libc.so.6").open("wb") as stream:
            stream.truncate(scanner.MAX_FILE_BYTES + 1)
        with self.assertRaises(scanner.BinaryInventoryBlocked):
            self._runtime()

    def test_directory_entry_cap_fails_closed(self):
        with patch.object(scanner, "MAX_ENTRIES_PER_DIRECTORY", 1):
            (self.bin / "ignored").touch()
            with self.assertRaises(scanner.BinaryInventoryBlocked):
                self._runtime()

    def test_bounded_file_and_total_byte_caps_fail_closed(self):
        with patch.object(scanner, "MAX_FILES", 1):
            with self.assertRaises(scanner.BinaryInventoryBlocked):
                self._runtime()
        with patch.object(scanner, "MAX_TOTAL_BYTES", len(self.busybox)):
            with self.assertRaises(scanner.BinaryInventoryBlocked):
                self._runtime()

    def test_main_emits_code_owned_failure_without_error_path_or_secrets(self):
        error = StringIO()
        with patch.object(scanner, "collect", side_effect=scanner.BinaryInventoryBlocked(
            "secret-path-and-token should not be printed"
        )), redirect_stderr(error):
            self.assertEqual(2, scanner.main())
        self.assertEqual("RUNTIME_BINARY_OBSERVATION_BLOCKED\n", error.getvalue())

    def test_exact_sha_image_python_os_gap_produces_explicit_partial_evidence(self):
        result = self._verify()
        self.assertEqual("goreecloud.search.local-selected-elf-file-hash-evidence.v1", result["schema"])
        self.assertEqual(IMAGE_ID, result["local_image_config_digest"])
        self.assertEqual("unavailable", result["package_inventory_status"])
        self.assertEqual("xbps", result["package_manager"])
        self.assertEqual(2, result["file_count"])
        self.assertEqual(self._runtime()["files"], result["files"])
        self.assertTrue(result["unsigned"])
        self.assertNotIn("packages", result)
        self.assertNotIn("package_count", result)
        self.assertIn("all_runtime_executables_libraries_symlinks_or_elf_dependency_closure",
                      result["not_evaluated"])

    def test_tampered_or_reordered_selected_runtime_rows_block(self):
        for change in (
            lambda x: x["files"].reverse(),
            lambda x: x["files"].append(deepcopy(x["files"][0])),
            lambda x: x["files"][0].update(path="/etc/passwd"),
            lambda x: x["files"][0].update(path="/usr/bin/../bin/busybox"),
            lambda x: x["files"][0].update(size_bytes=True),
            lambda x: x["files"][0].update(sha256="0" * 64 + "X"),
            lambda x: x.update(total_bytes_hashed=x["total_bytes_hashed"] + 1),
            lambda x: x.update(machine="aarch64"),
            lambda x: x.update(selection="all_binary_files"),
            lambda x: x.update(packages=[]),
        ):
            runtime = deepcopy(self._runtime())
            change(runtime)
            with self.subTest(change=str(change)), self.assertRaises(BinaryEvidenceError):
                self._verify(runtime)

    def test_previous_os_gap_evidence_tampering_blocks(self):
        for field, bad in (
            ("source_commit", "e" * 40),
            ("package_inventory_status", "available"),
            ("package_manager", "apk"),
            ("python_evidence_sha256", "0" * 64),
            ("unsigned", False),
            ("packages", []),
        ):
            with self.subTest(field=field):
                prior = deepcopy(OS_EVIDENCE)
                prior[field] = bad
                with self.assertRaises(BinaryEvidenceError):
                    self._verify(os_evidence=prior)

    def test_wrong_image_sha_architecture_source_or_python_chain_blocks(self):
        changes = (
            {"image": {**IMAGE, "local_image_config_digest": "sha256:" + "f" * 64}},
            {"image": {**IMAGE, "platform": "linux/arm64"}},
            {"image_id": "sha256:" + "f" * 64},
            {"sha": "e" * 40},
            {"source": {**SOURCE, "source_tree": "e" * 40}},
            {"python": {**PYTHON, "unsigned": False}},
            {"python": {**PYTHON, "distribution_manifest_sha256": "0" * 64}},
        )
        for change in changes:
            with self.subTest(change=str(change)), self.assertRaises(Exception):
                self._verify(**change)

    def test_full_os_package_list_is_not_a_substitute_for_void_gap(self):
        other = deepcopy(OS_EVIDENCE)
        other["schema"] = "goreecloud.search.local-os-package-evidence.v1"
        other.pop("package_inventory_status")
        with self.assertRaises(BinaryEvidenceError):
            self._verify(os_evidence=other)


if __name__ == "__main__":
    unittest.main()
