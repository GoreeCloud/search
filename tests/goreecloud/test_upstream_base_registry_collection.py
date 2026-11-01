"""Offline Docker Hub collector tests; no registry, Docker, or credential access."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from collect_upstream_base_manifest_evidence import (  # noqa: E402
    ACCEPT, AUTH_URL, REGISTRY, TAGS, ManifestEvidenceError, collect,
)
import collect_upstream_base_manifest_evidence as registry_collect  # noqa: E402


def encode(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def fixtures():
    store = {}
    for tag in TAGS:
        child = encode({
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {"mediaType": "application/vnd.oci.image.config.v1+json",
                       "digest": "sha256:" + "a" * 64, "size": 40},
            "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                        "digest": "sha256:" + "b" * 64, "size": 90}],
        })
        index = encode({
            "schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [{"mediaType": "application/vnd.oci.image.manifest.v1+json",
                           "digest": digest(child), "size": len(child),
                           "platform": {"os": "linux", "architecture": "amd64"}}],
        })
        store[tag] = index
        store[digest(child)] = child
    return store


class BoundedCollectorTests(unittest.TestCase):
    def transport(self, store, *, corrupt_header=None, wrong_type=None, unreachable=None):
        self.requested = []

        def fake(url, headers, deadline, budget):
            self.requested.append((url, headers, deadline, budget))
            if url == AUTH_URL:
                return {"Content-Type": "application/json"}, b'{"token":"test-only-token"}'
            self.assertTrue(url.startswith(REGISTRY))
            self.assertEqual("Bearer test-only-token", headers["Authorization"])
            self.assertEqual(ACCEPT, headers["Accept"])
            key = url[len(REGISTRY):]
            if key == unreachable:
                raise ManifestEvidenceError("bounded registry refusal")
            raw = store[key]
            item = json.loads(raw)
            return {
                "Content-Type": wrong_type or item["mediaType"],
                "Docker-Content-Digest": digest(raw) if corrupt_header is None else corrupt_header,
            }, raw
        return fake

    def test_both_tags_have_exact_immutable_index_child_closure(self):
        store = fixtures()
        result = collect(fetch=self.transport(store))
        self.assertEqual(set(TAGS), set(result))
        self.assertEqual(5, len(self.requested))
        self.assertEqual(AUTH_URL, self.requested[0][0])
        for tag in TAGS:
            item = result[tag]
            self.assertEqual(digest(item["raw_index"]),
                             item["evidence"]["verified_root_manifest_digest"])
            self.assertEqual(digest(item["raw_child"]),
                             item["evidence"]["verified_platform_child_digest"])
            self.assertEqual("index_child_digest_and_platform", item["evidence"]["platform_binding"])
            self.assertEqual("HOLD_NO_SEAL_OR_ANCHOR_QUALIFICATION", item["evidence"]["release_decision"])
        self.assertTrue(all("sha256:" in url or any(tag in url for tag in TAGS)
                            for url, *_ in self.requested[1:]))

    def test_malformed_registry_digest_header_denied(self):
        for header in ("", "sha256:" + "0" * 64, "not-a-digest"):
            with self.subTest(header=header):
                with self.assertRaisesRegex(ManifestEvidenceError, "digest response header"):
                    collect(fetch=self.transport(fixtures(), corrupt_header=header))

    def test_registry_content_type_does_not_override_raw_media_type(self):
        with self.assertRaisesRegex(ManifestEvidenceError, "content type"):
            collect(fetch=self.transport(fixtures(), wrong_type="application/json"))

    def test_expired_global_deadline_blocks_before_read(self):
        store = fixtures()

        def past(url, headers, deadline, budget):
            raise ManifestEvidenceError("deadline exceeded")

        with self.assertRaisesRegex(ManifestEvidenceError, "deadline"):
            collect(fetch=past)

    def test_runtime_failure_returns_no_partial_success(self):
        with self.assertRaisesRegex(ManifestEvidenceError, "bounded registry refusal"):
            collect(fetch=self.transport(fixtures(), unreachable="searxng"))

    def test_direct_manifest_tag_has_no_unsupported_platform_binding(self):
        store = fixtures()
        store["searxng-builder"] = store[next(k for k in store if k.startswith("sha256:"))]
        with self.assertRaisesRegex(ManifestEvidenceError, "platform index"):
            collect(fetch=self.transport(store))

    def test_wrong_descriptor_child_bytes_denied(self):
        store = fixtures()
        for key in list(store):
            if key.startswith("sha256:"):
                store[key] += b" "
        with self.assertRaisesRegex(ManifestEvidenceError, "unexpected child digest"):
            collect(fetch=self.transport(store))

    def test_missing_token_or_invalid_token_response_denied(self):
        for payload in (b"{}", b'{"token":"bad\\nheader"}', b"not-json", b'{"token":5}'):
            def fake(url, headers, deadline, budget):
                return {"Content-Type": "application/json"}, payload
            with self.subTest(payload=payload), self.assertRaises(ManifestEvidenceError):
                collect(fetch=fake)

    def test_transport_rejects_arbitrary_host_before_network(self):
        with self.assertRaisesRegex(ManifestEvidenceError, "external registry URL"):
            registry_collect._fetch("https://example.com/secret", {}, 9999999999, 50)

    def test_transport_deadline_fails_before_network(self):
        with self.assertRaisesRegex(ManifestEvidenceError, "deadline exceeded"):
            registry_collect._fetch(AUTH_URL, {}, 0, 50)

    def test_transport_rejects_oversized_response_body(self):
        class FakeResponse:
            status = 200
            headers = {"Content-Encoding": "identity", "Content-Length": "200"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        class FakeOpener:
            def open(self, req, timeout):
                return FakeResponse()

        with patch.object(registry_collect, "_OPENER", FakeOpener()):
            with self.assertRaisesRegex(ManifestEvidenceError, "byte budget"):
                registry_collect._fetch(AUTH_URL, {}, 9999999999, 100)

    def test_no_redirect_to_alternate_registry_host(self):
        with self.assertRaisesRegex(ManifestEvidenceError, "redirect refused"):
            registry_collect._RejectRedirect().redirect_request(
                None, None, 302, "Moved", {}, "https://example.com/")

    def test_cli_existing_destination_blocked_without_network(self):
        script = ROOT / "scripts/collect_upstream_base_manifest_evidence.py"
        result = subprocess.run([sys.executable, str(script), "--output-dir", str(ROOT)],
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(2, result.returncode)
        self.assertIn("COLLECTION_BLOCKED", result.stderr)

    def test_invalid_platform_is_denied_before_fetch(self):
        def must_not_fetch(*args):
            self.fail("collector attempted network before platform validation")
        with self.assertRaisesRegex(ManifestEvidenceError, "platform"):
            collect("bad platform", fetch=must_not_fetch)


if __name__ == "__main__":
    unittest.main()
