"""Offline package-inventory and exact-image binding regression tests."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime_python_inventory import InventoryError, collect, normalize_name
from verify_runtime_python_inventory import DependencyEvidenceError, verify


SOURCE_SHA = "a" * 40
IMAGE_ID = "sha256:" + "b" * 64
SOURCE = {
    "source_tree": "c" * 40,
    "input_sha256": {"requirements.txt": "d" * 64},
}
IMAGE = {
    "schema": "goreecloud.search.local-image-candidate.v1",
    "repository": "https://github.com/GoreeCloud/search",
    "source_commit": SOURCE_SHA,
    "source_tree": SOURCE["source_tree"],
    "release_input_sha256": SOURCE["input_sha256"],
    "local_image_config_digest": IMAGE_ID,
    "image_tag": f"goreecloud/search:staging-{SOURCE_SHA[:12]}",
    "platform": "linux/amd64",
    "unsigned": True,
}
RUNTIME = {
    "schema": "goreecloud.search.runtime-python-distributions.v1",
    "python_version": "3.12.7",
    "implementation": "CPython",
    "os": "linux",
    "machine": "x86_64",
    "distributions": [
        {"name": "aiohttp", "version": "3.11.13"},
        {"name": "granian", "version": "2.8.4"},
    ],
}


class Dist:
    def __init__(self, name, version):
        self.metadata = {"Name": name}
        self.version = version


class RuntimePythonInventoryTests(unittest.TestCase):
    def test_stdlib_inventory_is_sorted_and_contains_only_names_versions(self):
        result = collect([Dist("Granian", "2.8.4"), Dist("aiohttp", "3.11.13")])
        self.assertEqual(RUNTIME["distributions"], result["distributions"])
        self.assertEqual("goreecloud.search.runtime-python-distributions.v1", result["schema"])
        self.assertEqual("CPython", result["implementation"])

    def test_normalization_rejects_duplicate_aliases(self):
        self.assertEqual("my-package", normalize_name("My_Package"))
        with self.assertRaises(InventoryError):
            collect([Dist("A_B", "1.0"), Dist("a-b", "1.0")])

    def test_invalid_or_empty_distribution_inventory_blocks(self):
        for packages in ([], [Dist("name with spaces", "1.0")],
                         [Dist("valid", "not a version")], [Dist("bad/name", "1.0")]):
            with self.subTest(packages=packages):
                with self.assertRaises(InventoryError):
                    collect(packages)

    def test_valid_exact_image_observation_is_explicitly_partial_unsigned(self):
        evidence = verify(deepcopy(RUNTIME), deepcopy(IMAGE), deepcopy(SOURCE), SOURCE_SHA, IMAGE_ID)
        self.assertEqual(2, evidence["distribution_count"])
        self.assertEqual(64, len(evidence["distribution_manifest_sha256"]))
        self.assertTrue(evidence["unsigned"])
        self.assertIn("complete_sbom_licenses_and_vulnerabilities", evidence["not_evaluated"])
        self.assertEqual(IMAGE_ID, evidence["local_image_config_digest"])

    def test_mismatched_source_manifest_and_image_id_block(self):
        for field, value in (("source_commit", "f" * 40),
                             ("source_tree", "0" * 40),
                             ("local_image_config_digest", "sha256:" + "e" * 64),
                             ("unsigned", False),
                             ("platform", "linux/s390x")):
            with self.subTest(field=field):
                image = deepcopy(IMAGE)
                image[field] = value
                with self.assertRaises(DependencyEvidenceError):
                    verify(RUNTIME, image, SOURCE, SOURCE_SHA, IMAGE_ID)

    def test_wrong_exact_source_inputs_block(self):
        altered = deepcopy(SOURCE)
        altered["input_sha256"]["requirements.txt"] = "e" * 64
        with self.assertRaises(DependencyEvidenceError):
            verify(RUNTIME, IMAGE, altered, SOURCE_SHA, IMAGE_ID)

    def test_runtime_platform_and_interpreter_mismatch_block(self):
        for field, value in (("machine", "aarch64"), ("os", "win32"),
                             ("implementation", "PyPy"), ("python_version", "unknown")):
            with self.subTest(field=field):
                runtime = deepcopy(RUNTIME)
                runtime[field] = value
                with self.assertRaises(DependencyEvidenceError):
                    verify(runtime, IMAGE, SOURCE, SOURCE_SHA, IMAGE_ID)

    def test_ambiguous_or_malformed_packages_block(self):
        cases = (
            [],
            [{"name": "aiohttp", "version": "3.11.13"}] * 2,
            [{"name": "UPPER", "version": "1.0"}],
            [{"name": "bad name", "version": "1.0"}],
            [{"name": "okay", "version": "bad version"}],
            [{"name": "okay", "version": "1.0", "url": "https://example.invalid"}],
            [{"name": "zebra", "version": "1.0"}, {"name": "alpha", "version": "1.0"}],
        )
        for packages in cases:
            with self.subTest(packages=packages):
                runtime = deepcopy(RUNTIME)
                runtime["distributions"] = packages
                with self.assertRaises(DependencyEvidenceError):
                    verify(runtime, IMAGE, SOURCE, SOURCE_SHA, IMAGE_ID)

    def test_reject_runtime_fields_that_could_disclose_unnecessary_metadata(self):
        runtime = deepcopy(RUNTIME)
        runtime["site_packages_path"] = "/opt/secret/never-retain"
        with self.assertRaises(DependencyEvidenceError):
            verify(runtime, IMAGE, SOURCE, SOURCE_SHA, IMAGE_ID)

    def test_malformed_image_digest_blocks(self):
        with self.assertRaises(DependencyEvidenceError):
            verify(RUNTIME, IMAGE, SOURCE, SOURCE_SHA, "sha256:short")


if __name__ == "__main__":
    unittest.main()
