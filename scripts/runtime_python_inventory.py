#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit installed Python distribution names and versions from this interpreter.

Run only in a disposable, no-network, read-only candidate-image container.
This intentionally omits distribution metadata that can contain URLs, paths,
licenses or other extraneous material. It is NOT a full SBOM or audit.
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import re
import sys


NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+!-]{0,127}\Z")
MAX_DISTRIBUTIONS = 4096


class InventoryError(Exception):
    """An installed distribution cannot be unambiguously inventoried."""


def normalize_name(value: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise InventoryError("invalid Python distribution name")
    return re.sub(r"[-_.]+", "-", value).lower()


def collect(distributions=None) -> dict:
    if distributions is None:
        distributions = importlib.metadata.distributions()
    packages = {}
    for dist in distributions:
        if len(packages) >= MAX_DISTRIBUTIONS:
            raise InventoryError("Python distribution inventory exceeds bound")
        name = normalize_name(dist.metadata.get("Name"))
        version = dist.version
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise InventoryError("invalid Python distribution version")
        if name in packages:
            raise InventoryError("duplicate normalized Python distribution")
        packages[name] = version
    if not packages:
        raise InventoryError("no installed Python distributions found")
    return {
        "schema": "goreecloud.search.runtime-python-distributions.v1",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "implementation": platform.python_implementation(),
        "os": sys.platform,
        "machine": platform.machine(),
        "distributions": [
            {"name": name, "version": packages[name]} for name in sorted(packages)
        ],
    }


def main() -> int:
    try:
        print(json.dumps(collect(), separators=(",", ":"), sort_keys=True))
    except (InventoryError, OSError, ValueError, TypeError):
        print("PYTHON_DISTRIBUTION_INVENTORY_BLOCKED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
