"""Offline exact-source Dockerfile base-reference/negative release-gate tests."""

import hashlib
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_dockerfile_base_refs import (  # noqa: E402
    BaseReferenceError, DOCKERFILES, REPO_URL, audit, scan,
)


def fixture(files):
    source = {
        "schema": "goreecloud.search.source-baseline.v1",
        "repository": REPO_URL,
        "source_commit": "a" * 40,
        "source_tree": "b" * 40,
        "input_sha256": {key: hashlib.sha256(contents).hexdigest()
                         for key, contents in files.items()},
    }
    return audit(source, files)


class DockerfileBaseReferenceAuditTests(unittest.TestCase):
    def test_current_exact_dockerfiles_disclose_three_dynamic_froms(self):
        files = {path: (ROOT / path).read_bytes() for path in DOCKERFILES}
        report = fixture(files)
        rows = report["from_references"]
        self.assertEqual(3, len(rows))
        self.assertEqual(3, report["unresolved_or_mutable_reference_count"])
        self.assertEqual(["unresolved_build_argument"] * 3,
                         [r["classification"] for r in rows])
        # The audit sees checked-in defaults, not any actual build-arg override.
        self.assertEqual(["${BUILDER_BASE_IMAGE}", "${BUILDER_IMAGE}",
                          "${RUNTIME_BASE_IMAGE}"], [r["reference"] for r in rows])
        self.assertEqual("HOLD_NO_SEAL_OR_ANCHOR_QUALIFICATION", report["release_decision"])
        self.assertIn("upstream_image_licenses_vulnerabilities_or_complete_sbom",
                      report["not_evaluated"])

    def test_digest_syntax_and_local_stage_are_not_mistaken_for_release_evidence(self):
        pinned = b"FROM --platform=$TARGETPLATFORM docker.io/example/base@sha256:" + b"f" * 64 + b" AS compile\nFROM compile AS final\n"
        files = {DOCKERFILES[0]: pinned, DOCKERFILES[1]: b"FROM scratch AS dist\n"}
        report = fixture(files)
        self.assertEqual(0, report["unresolved_or_mutable_reference_count"])
        self.assertEqual(
            ["digest_syntax_only_unverified", "prior_local_stage", "empty_scratch_base"],
            [r["classification"] for r in report["from_references"]],
        )
        self.assertEqual("HOLD_NO_SEAL_OR_ANCHOR_QUALIFICATION", report["release_decision"])
        self.assertIn("digest syntax alone", report["blocking_reasons"][0])

    def test_changed_source_or_missing_dockerfile_fails_closed(self):
        files = {path: b"FROM docker.io/example:mutable\n" for path in DOCKERFILES}
        wrong = {
            "schema": "goreecloud.search.source-baseline.v1",
            "repository": REPO_URL,
            "source_commit": "a" * 40,
            "source_tree": "b" * 40,
            "input_sha256": {key: "0" * 64 for key in DOCKERFILES},
        }
        with self.assertRaisesRegex(BaseReferenceError, "differs"):
            audit(wrong, files)
        with self.assertRaisesRegex(BaseReferenceError, "incomplete"):
            audit(wrong, {DOCKERFILES[0]: files[DOCKERFILES[0]]})

    def test_malformed_or_unsupported_from_fails_closed(self):
        invalid = (
            b"FROM base@sha256:short\n",
            b"FROM --platform= docker.io/base:tag\n",
            b"FROM --mystery=flag docker.io/base:tag\n",
            b"FROM docker.io/base:tag AS stage AS again\n",
            b"FROM base AS repeat\nFROM other AS repeat\n",
            b"FROM docker.io/example\\\n:tag\n",
            b"FROM docker.io/base:tag # trailing content\n",
            b"RUN echo no parent\n",
            b"FROM something/\xff\n",
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(BaseReferenceError):
                scan(DOCKERFILES[0], raw)

    def test_boundaries_reject_unbounded_or_empty_dockerfiles(self):
        for raw in (b"", b"# only a comment\n", b"FROM " + b"x" * 9000,
                    b"FROM image\n" * 33):
            with self.subTest(size=len(raw)), self.assertRaises(BaseReferenceError):
                scan(DOCKERFILES[0], raw)


if __name__ == "__main__":
    unittest.main()
