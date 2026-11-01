"""Offline, fail-closed checks for a local image/source identity record."""

import sys
from copy import deepcopy
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from candidate_image_evidence import ImageEvidenceError, REPO_URL, verify


SHA = "a" * 40
ID = "sha256:" + "b" * 64
TAG = f"goreecloud/search:staging-{SHA[:12]}"
BASELINE = {
    "schema": "goreecloud.search.source-baseline.v1",
    "repository": REPO_URL,
    "source_commit": SHA,
    "source_tree": "c" * 40,
    "input_sha256": {"requirements.txt": "d" * 64},
    "evidence_scope": "exact_clean_source_checkout_only",
}
INSPECT = [{
    "Id": ID,
    "RepoTags": [TAG],
    "Os": "linux",
    "Architecture": "amd64",
    "Config": {"Labels": {
        "org.opencontainers.image.revision": SHA,
        "org.opencontainers.image.source": REPO_URL,
        "org.opencontainers.image.version": f"dev-{SHA[:12]}",
    }},
}]


class CandidateImageEvidenceTests(unittest.TestCase):
    def test_clean_exact_source_and_image_emit_explicitly_unsigned_evidence(self):
        record = verify(BASELINE, deepcopy(BASELINE), deepcopy(INSPECT), SHA)
        self.assertEqual(ID, record["local_image_config_digest"])
        self.assertEqual(TAG, record["image_tag"])
        self.assertEqual("c" * 40, record["source_tree"])
        self.assertTrue(record["unsigned"])
        self.assertIn("deployed_image_identity_and_rollback_artifact", record["not_evaluated"])
        self.assertNotIn("signed", record)

    def test_reject_changed_source_inventory(self):
        changed = deepcopy(BASELINE)
        changed["input_sha256"]["requirements.txt"] = "0" * 64
        with self.assertRaises(ImageEvidenceError):
            verify(changed, BASELINE, INSPECT, SHA)

    def test_reject_changed_requested_source_sha(self):
        with self.assertRaises(ImageEvidenceError):
            verify(BASELINE, BASELINE, INSPECT, "e" * 40)

    def test_reject_missing_or_forged_revision_source_and_version(self):
        for label, value in (
            ("org.opencontainers.image.revision", "e" * 40),
            ("org.opencontainers.image.source", "https://github.com/Other/search"),
            ("org.opencontainers.image.version", "dev-deadbeef"),
        ):
            with self.subTest(label=label):
                inspected = deepcopy(INSPECT)
                inspected[0]["Config"]["Labels"][label] = value
                with self.assertRaises(ImageEvidenceError):
                    verify(BASELINE, BASELINE, inspected, SHA)

    def test_reject_unrelated_tag_and_malformed_image_id(self):
        for field, value in (("RepoTags", ["goreecloud/search:latest"]),
                             ("RepoTags", f"prefix-{TAG}-suffix"),
                             ("Id", "sha256:" + "z" * 64)):
            with self.subTest(field=field):
                inspected = deepcopy(INSPECT)
                inspected[0][field] = value
                with self.assertRaises(ImageEvidenceError):
                    verify(BASELINE, BASELINE, inspected, SHA)

    def test_reject_empty_ambiguous_or_malformed_inspect(self):
        for inspected in ([], INSPECT + INSPECT, [{}], {}, None):
            with self.subTest(inspected=inspected):
                with self.assertRaises(ImageEvidenceError):
                    verify(BASELINE, BASELINE, inspected, SHA)

    def test_reject_unexpected_platform_or_absent_labels(self):
        for key, value in (("Architecture", "unknown"), ("Os", "windows"),
                           ("Config", {})):
            with self.subTest(key=key):
                inspected = deepcopy(INSPECT)
                inspected[0][key] = value
                with self.assertRaises(ImageEvidenceError):
                    verify(BASELINE, BASELINE, inspected, SHA)


if __name__ == "__main__":
    unittest.main()
