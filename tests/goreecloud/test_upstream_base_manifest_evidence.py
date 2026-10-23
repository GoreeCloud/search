"""Bounded synthetic raw-manifest provenance checks; no registry or Docker access."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_upstream_base_manifest import ManifestEvidenceError, verify  # noqa: E402


def encode(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def digest(obj):
    return "sha256:" + hashlib.sha256(obj).hexdigest()


def image_manifest():
    return encode({
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {"mediaType": "application/vnd.oci.image.config.v1+json",
                   "digest": "sha256:" + "a" * 64, "size": 42},
        "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                    "digest": "sha256:" + "b" * 64, "size": 789}],
    })


def index_manifest(child, duplicate=False):
    entry = {"mediaType": "application/vnd.oci.image.manifest.v1+json",
             "digest": digest(child), "size": len(child),
             "platform": {"os": "linux", "architecture": "amd64"}}
    return encode({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json",
                   "manifests": [entry, entry] if duplicate else [entry]})


def ref(raw):
    return "docker.io/searxng/base@" + digest(raw)


class UpstreamBaseManifestEvidenceTests(unittest.TestCase):
    def test_digest_checked_index_to_platform_specific_child(self):
        child = image_manifest()
        root = index_manifest(child)
        result = verify(ref(root), root, child, "linux/amd64")
        self.assertEqual(digest(root), result["verified_root_manifest_digest"])
        self.assertEqual(digest(child), result["verified_platform_child_digest"])
        self.assertEqual("index_child_digest_and_platform", result["platform_binding"])
        self.assertEqual(1, result["image_layer_descriptor_count"])
        self.assertEqual("HOLD_NO_SEAL_OR_ANCHOR_QUALIFICATION", result["release_decision"])

    def test_single_image_digest_has_no_platform_proof(self):
        raw = image_manifest()
        item = verify(ref(raw), raw, None, "linux/amd64")
        self.assertIsNone(item["verified_platform_child_digest"])
        self.assertEqual("NOT_VERIFIED_DIRECT_MANIFEST", item["platform_binding"])

    def test_wrong_digest_reformatted_json_or_changed_child_rejected(self):
        child = image_manifest()
        root = index_manifest(child)
        for bad in (ref(root)[:-1] + "0", "docker.io/searxng/base:tag",
                    "docker.io/attacker/base@" + digest(root)):
            if bad == ref(root):
                continue
            with self.subTest(ref=bad), self.assertRaises(ManifestEvidenceError):
                verify(bad, root, child, "linux/amd64")
        with self.assertRaisesRegex(ManifestEvidenceError, "child bytes"):
            verify(ref(root), root, child + b" ", "linux/amd64")
        # A semantically identical JSON reserialization is NOT registry digest evidence.
        pretty = json.dumps(json.loads(root), indent=2).encode()
        with self.assertRaisesRegex(ManifestEvidenceError, "top-level"):
            verify(ref(root), pretty, child, "linux/amd64")

    def test_wrong_platform_missing_child_and_ambiguous_child_rejected(self):
        child = image_manifest()
        root = index_manifest(child)
        for platform, supplied in (("linux/arm64", child), ("linux/amd64", None),
                                   ("windows/amd64", child)):
            with self.subTest(platform=platform), self.assertRaisesRegex(
                    ManifestEvidenceError, "missing or ambiguous"):
                verify(ref(root), root, supplied, platform)
        duplicate = index_manifest(child, duplicate=True)
        with self.assertRaisesRegex(ManifestEvidenceError, "ambiguous"):
            verify(ref(duplicate), duplicate, child, "linux/amd64")

    def test_malformed_or_unbounded_data_fails_closed(self):
        child = image_manifest()
        mutations = [
            b'{"schemaVersion":2,"schemaVersion":2,"mediaType":"' +
            b'application/vnd.oci.image.manifest.v1+json"}',
            b"not-json", b"", b"\xff", b" " * (2 * 1024 * 1024 + 1),
            encode({"schemaVersion": True, "mediaType": "application/vnd.oci.image.manifest.v1+json"}),
            encode({"schemaVersion": 2, "mediaType": "application/unknown"}),
        ]
        for raw in mutations:
            with self.subTest(size=len(raw)), self.assertRaises(ManifestEvidenceError):
                verify(ref(raw), raw, None, "linux/amd64")
        malformed_layers = json.loads(child)
        malformed_layers["layers"][0]["urls"] = ["https://attacker.test/layer"]
        raw = encode(malformed_layers)
        with self.assertRaisesRegex(ManifestEvidenceError, "external"):
            verify(ref(raw), raw, None, "linux/amd64")

    def test_cli_emits_nonpromoting_evidence_and_never_overwrites(self):
        child = image_manifest()
        root = index_manifest(child)
        script = ROOT / "scripts/verify_upstream_base_manifest.py"
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "index.json").write_bytes(root)
            (base / "child.json").write_bytes(child)
            args = [sys.executable, str(script), "--base-ref", ref(root),
                    "--root-raw", str(base / "index.json"),
                    "--child-raw", str(base / "child.json"),
                    "--platform", "linux/amd64", "--output", str(base / "evidence.json")]
            good = subprocess.run(args, capture_output=True, text=True, timeout=5)
            self.assertEqual(0, good.returncode, good.stderr)
            evidence = json.loads((base / "evidence.json").read_text())
            self.assertEqual("HOLD_NO_SEAL_OR_ANCHOR_QUALIFICATION", evidence["release_decision"])
            again = subprocess.run(args, capture_output=True, text=True, timeout=5)
            self.assertEqual(2, again.returncode)
            self.assertEqual(evidence, json.loads((base / "evidence.json").read_text()))


if __name__ == "__main__":
    unittest.main()
