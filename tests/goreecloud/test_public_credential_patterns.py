"""Bounded offline credential-pattern check of the public Git HEAD tree.

This is a source-only regression gate, not a historical or exhaustive secret audit.
Never include matched credential values in failure messages.
"""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
RULES = {
    "google-api-key": re.compile("AI" + "za" + r"[A-Za-z0-9_-]{35}"),
    "github-classic": re.compile("gh" + r"[pousr]_[A-Za-z0-9_]{28,}"),
    "github-fine-grained": re.compile("github_" + "pat_" + r"[A-Za-z0-9_]{25,}"),
    "aws-access-key": re.compile("AK" + "IA" + r"[A-Z0-9]{16}"),
    "private-key-block": re.compile("-" * 5 + "BEGIN " + r"(?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY" + "-" * 5),
}

class PublicCredentialPatternTests(unittest.TestCase):
    def test_google_key_detector_is_active(self):
        sample = "AI" + "za" + "A" * 35
        self.assertIsNotNone(RULES["google-api-key"].search(sample))

    def test_tracked_public_tree_contains_no_recognized_credentials(self):
        paths = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", "-z"], timeout=20
        ).split(b"\0")
        self.assertGreater(len(paths), 5)
        suspects = []
        for raw in paths:
            if not raw:
                continue
            relative = raw.decode("utf-8")
            path = ROOT / relative
            if path.is_symlink() or not path.is_file():
                continue
            try:
                raw_content = path.read_bytes()
                if len(raw_content) > 5_000_000 or b"\0" in raw_content[:1024]:
                    continue
                content = raw_content.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for name, rule in RULES.items():
                if rule.search(content):
                    suspects.append(f"{relative} [{name}]")
        self.assertFalse(suspects, "Potential embedded public-tree credentials (values withheld): " +
                         ", ".join(suspects[:15]))

if __name__ == "__main__":
    unittest.main()
