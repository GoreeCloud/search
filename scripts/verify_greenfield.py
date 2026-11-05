"""Fail-closed offline greenfield integration gate (no live providers)."""
from __future__ import annotations

import ast
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
MIN_TESTS = 150  # Enforce current integrated regression baseline including localdomain isolation.

# The rejected Search recovery tree must not return as a second implementation.
# Explicit source roots are guarded without banning documentation that discusses
# the historical incident or the separately hosted SearXNG HTTP connector.
RETIRED_ROOTS = frozenset({
    "searx", "searxng", "searxng-docker", "searx-recovery",
    "legacy-search", "recovered-search", "legacy_search",
})
RETIRED_IMPORTS = frozenset({"searx", "searxng"})


def legacy_source_violations(root: Path) -> list[str]:
    """Detect known forbidden source roots and direct retired package imports.

    This is a narrow regression gate, not a proof of intellectual-property
    provenance or a comprehensive software composition audit.
    """
    problems: list[str] = []
    try:
        for item in root.iterdir():
            if item.name.casefold() in RETIRED_ROOTS:
                problems.append("Retired Search source root detected: " + item.name)
    except OSError:
        return ["Cannot inspect Search source root"]

    package = root / "goreecloud_search"
    if package.is_symlink() or not package.is_dir():
        return problems + ["Missing or symlinked first-party Search package"]
    for source in sorted(package.rglob("*.py")):
        label = source.relative_to(root).as_posix()
        if source.is_symlink():
            problems.append("Symlinked Search source: " + label)
            continue
        try:
            syntax = ast.parse(source.read_text(encoding="utf-8"), filename=label)
        except (OSError, UnicodeError, SyntaxError):
            problems.append("Unreadable or invalid Search source: " + label)
            continue
        for node in ast.walk(syntax):
            if isinstance(node, ast.Import):
                imports = (item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imports = (node.module or "",)
            else:
                continue
            if any(module.split(".", 1)[0] in RETIRED_IMPORTS for module in imports):
                problems.append("Retired package import: " + label)
                break
    return problems


def main() -> int:
    violations = legacy_source_violations(ROOT)
    if violations:
        for issue in violations:
            print(issue, file=sys.stderr)
        return 2
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
