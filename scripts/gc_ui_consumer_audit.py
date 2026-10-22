#!/usr/bin/env python3
"""Report and constrain Search's remaining active legacy UI dependencies.

This is an inventory gate, *not* proof of GoreeCloud UI conformance.  Legacy
vendor assets are reported separately from the first-party consumer surfaces.
"""

import argparse
import json
import re
from pathlib import Path


LEGACY_TOKEN = re.compile(r"glaze|\bglz[0-9]", re.IGNORECASE)
ACTIVE_ROOTS = ("searx/templates", "searx/static")
SOURCE_SUFFIXES = frozenset((".html", ".css", ".js"))
DEFAULT_BASELINE = "docs/goreecloud/gc-ui-legacy-baseline.json"
VENDORED_ROOT = "searx/static/themes/simple/glaze"


def inventory(repo_root):
    """Count lines using retired tokens in shipped first-party Search UI code."""
    result = {}
    for relative_root in ACTIVE_ROOTS:
        for path in sorted((repo_root / relative_root).rglob("*")):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            relative_path = path.relative_to(repo_root)
            if "glaze" in relative_path.parts:
                continue  # Inventory the bundled legacy CSS separately.
            lines = path.read_text(encoding="utf-8").splitlines()
            matches = sum(bool(LEGACY_TOKEN.search(line)) for line in lines)
            if matches:
                result[relative_path.as_posix()] = matches
    return result


def assess(observed, allowed, strict=False):
    """Fail on new/expanded legacy use; optionally require zero active use."""
    regressions = {}
    for path, count in observed.items():
        allowance = allowed.get(path, 0)
        if count > allowance:
            regressions[path] = {"observed": count, "maximum": allowance}
    if strict and observed:
        return False, regressions
    return not regressions, regressions


def audit(repo_root, baseline_path, strict=False):
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    allowed = baseline["maximum_active_legacy_lines"]
    if not isinstance(allowed, dict) or any(
        not isinstance(path, str) or type(count) is not int or count < 0
        for path, count in allowed.items()
    ):
        raise ValueError("Invalid GC UI legacy baseline")
    observed = inventory(repo_root)
    passed, regressions = assess(observed, allowed, strict=strict)
    legacy_vendor_css = len(list((repo_root / VENDORED_ROOT).rglob("*.css")))
    return {
        "passed": passed,
        "mode": "strict" if strict else "no-new-legacy",
        "active_files": observed,
        "active_legacy_lines": sum(observed.values()),
        "baseline_active_legacy_lines": sum(allowed.values()),
        "vendor_legacy_css_files": legacy_vendor_css,
        "regressions": regressions,
        "full_gc_ui_acceptance": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", type=Path, default=Path(DEFAULT_BASELINE))
    parser.add_argument("--strict", action="store_true", help="Fail until all active legacy references are removed")
    parser.add_argument("--json", action="store_true", help="Print the full machine-readable inventory")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    baseline = args.baseline if args.baseline.is_absolute() else root / args.baseline
    try:
        report = audit(root, baseline, strict=args.strict)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, "GC UI legacy audit unavailable: {}\n".format(exc))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("GC UI migration gate: {} ({} active legacy lines in {} first-party files; {} bundled CSS files)".format(
            "PASS" if report["passed"] else "FAIL", report["active_legacy_lines"],
            len(report["active_files"]), report["vendor_legacy_css_files"]
        ))
        for path, details in report["regressions"].items():
            print("  New/expanded legacy dependency: {} ({} > {})".format(
                path, details["observed"], details["maximum"]
            ))
        if args.strict and report["active_files"]:
            print("  Strict GC UI migration gate remains open: active legacy tokens exist")
        print("  This audit does not certify GC UI visual, accessibility, or native acceptance")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
