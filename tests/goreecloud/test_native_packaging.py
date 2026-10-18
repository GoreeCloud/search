"""Ensure native code ships in the Development container image."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]

class NativePackagingTests(unittest.TestCase):
    def test_native_adapter_is_not_docker_ignored(self):
        self.assertIn('!native_search/**',(ROOT/'.dockerignore').read_text().splitlines())
        self.assertIn('COPY --chown=977:977 ./native_search/ ./native_search/',
                      (ROOT/'container/dist.dockerfile').read_text())
