"""Fail-closed offline greenfield integration gate (no live providers)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "goreecloud_search/server.py",
    "goreecloud_search/links.py",
    "goreecloud_search/store.py",
    "goreecloud_search/providers.py",
    "goreecloud_search/federation.py",
    "goreecloud_search/native.py",
    "goreecloud_search/request_budget.py",
    "goreecloud_search/recovery.py",
    "scripts/package_native.py",
    "web/index.html",
    "web/app.js",
    "web/styles.css",
    "tests/test_search.py",
    "tests/test_store_security.py",
    "tests/test_quickstart.py",
    "tests/test_import_security.py",
    "tests/test_optional_providers.py",
    "tests/test_http_integration.py",
    "tests/test_ui_contract.py",
    "tests/test_native.py",
    "tests/test_request_budget.py",
    "tests/test_native_archive.py",
    "tests/test_recovery.py",
    "tests/test_contrast.py",
    "tests/test_http_strict_json.py",
    "tests/test_readiness.py",
    "tests/test_links.py",
)
MIN_TESTS = 133  # 130 prior plus three import-source ancestry and CLI-relative path checks.


def main() -> int:
    for name in REQUIRED:
        target = ROOT / name
        if not target.is_file() or target.is_symlink():
            print(f"Missing or symlinked required source: {name}", file=sys.stderr)
            return 2
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    count = suite.countTestCases()
    if count < MIN_TESTS:
        print(f"Insufficient integrated tests: {count}; require {MIN_TESTS}", file=sys.stderr)
        return 2
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped or result.testsRun < MIN_TESTS:
        print(
            f"Integration failed: {result.testsRun} run, {len(result.skipped)} skipped",
            file=sys.stderr,
        )
        return 1
    print(f"Greenfield integration validated: {result.testsRun} offline tests, zero skips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
