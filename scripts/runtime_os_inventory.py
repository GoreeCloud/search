#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Observe OS package-manager records or an explicitly stripped Void runtime.

Only preselected OS metadata and package database paths are inspected. There
is no network, subprocess, installation, application import or token access.
The Void SearXNG base deliberately removes its XBPS registry; that observation
is NOT an inventory of installed packages or a complete SBOM.
"""

from __future__ import annotations

import json
from pathlib import Path
import platform
import re
import sys


MAX_DATABASE_BYTES = 16 * 1024 * 1024
MAX_PACKAGES = 12000
PACKAGE_NAME = re.compile(r"[a-z0-9][a-z0-9+._-]{0,127}\Z")
PACKAGE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+:~_!-]{0,191}\Z")
PACKAGE_ARCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9_+-]{0,31}\Z")
RELEASE_FIELD = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
RELEASE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}\Z")


class InventoryError(Exception):
    """The observed OS package database cannot be safely inventoried."""


def _read_bounded(path: Path) -> str:
    try:
        with path.open("rb") as source:
            data = source.read(MAX_DATABASE_BYTES + 1)
        if len(data) > MAX_DATABASE_BYTES:
            raise InventoryError("OS package database exceeds the size budget")
        return data.decode("utf-8")
    except (UnicodeDecodeError, OSError):
        raise InventoryError("OS package metadata is unreadable or malformed") from None


def _entry(name: str, version: str, arch: str) -> dict[str, str]:
    if (not isinstance(name, str) or not PACKAGE_NAME.fullmatch(name)
            or not isinstance(version, str) or not PACKAGE_VERSION.fullmatch(version)
            or not isinstance(arch, str) or not PACKAGE_ARCH.fullmatch(arch)):
        raise InventoryError("OS package has an invalid name, version or architecture")
    return {"name": name, "version": version, "arch": arch}


def _canonical(packages: list[dict[str, str]]) -> list[dict[str, str]]:
    if not 0 < len(packages) <= MAX_PACKAGES:
        raise InventoryError("OS package count is empty or too large")
    packages.sort(key=lambda p: (p["name"], p["arch"]))
    if len({(p["name"], p["arch"]) for p in packages}) != len(packages):
        raise InventoryError("duplicate installed OS package name/architecture")
    return packages


def parse_dpkg_status(contents: str) -> list[dict[str, str]]:
    """Inspect only installed records in Debian's text status database."""
    if not isinstance(contents, str):
        raise InventoryError("dpkg status data is not text")
    records = []
    for paragraph in re.split(r"\n\s*\n", contents.strip()):
        if not paragraph:
            continue
        fields: dict[str, str] = {}
        for line in paragraph.splitlines():
            if line.startswith((" ", "\t")):
                continue  # RFC822 continuation fields are not package identity.
            if ": " not in line:
                raise InventoryError("malformed dpkg status field")
            key, value = line.split(": ", 1)
            if key in ("Package", "Version", "Architecture", "Status"):
                if key in fields:
                    raise InventoryError("duplicate dpkg identity field")
                fields[key] = value.strip()
        if fields.get("Status") == "install ok installed":
            if any(key not in fields for key in ("Package", "Version", "Architecture")):
                raise InventoryError("installed dpkg record lacks package identity")
            records.append(_entry(fields["Package"], fields["Version"], fields["Architecture"]))
    return _canonical(records)


def parse_apk_installed(contents: str) -> list[dict[str, str]]:
    """Inspect APK's text installed database without executing apk."""
    if not isinstance(contents, str):
        raise InventoryError("apk installed data is not text")
    records = []
    for paragraph in re.split(r"\n\s*\n", contents.strip()):
        if not paragraph:
            continue
        fields: dict[str, str] = {}
        for line in paragraph.splitlines():
            if line.startswith((" ", "\t")):
                continue
            if not re.match(r"^[A-Za-z]:", line):
                raise InventoryError("malformed apk installed field")
            key, value = line[:1], line[2:]
            if key in ("P", "V", "A"):
                if key in fields:
                    raise InventoryError("duplicate apk identity field")
                fields[key] = value.strip()
        if any(key not in fields for key in ("P", "V", "A")):
            raise InventoryError("apk record lacks package identity")
        records.append(_entry(fields["P"], fields["V"], fields["A"]))
    return _canonical(records)


def parse_os_release(contents: str) -> dict[str, str | None]:
    fields: dict[str, str] = {}
    for line in contents.splitlines():
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise InventoryError("malformed os-release field")
        key, value = line.split("=", 1)
        if key in ("ID", "VERSION_ID"):
            if key in fields:
                raise InventoryError("duplicate os-release identity field")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            fields[key] = value
    if not RELEASE_FIELD.fullmatch(fields.get("ID", "")):
        raise InventoryError("OS release identity missing or invalid")
    # Rolling-release Void legitimately omits VERSION_ID. No other OS may omit
    # it, and only that exact absence may enter the stripped-registry branch.
    version_id = fields.get("VERSION_ID")
    if version_id is None:
        if fields["ID"] != "void":
            raise InventoryError("OS release identity missing or invalid")
    elif not RELEASE_VERSION.fullmatch(version_id):
        raise InventoryError("OS release identity missing or invalid")
    return {"id": fields["ID"], "version_id": version_id}


def _xbps_registry_absent(root: Path) -> bool:
    """Check for XBPS registration files, including unexpected xbps* entries.

    The known SearXNG Void runtime explicitly removes /var/db, but avoid
    silently misclassifying future images that retain XBPS state.
    """
    database_root = root / "var/db"
    if database_root.is_symlink() or (database_root.exists() and not database_root.is_dir()):
        raise InventoryError("Void package registry path is ambiguous")
    if not database_root.exists():
        return True
    try:
        return not any(entry.name.lower().startswith("xbps") for entry in database_root.iterdir())
    except OSError:
        raise InventoryError("Void package registry path is unreadable") from None


def collect(root: Path = Path("/")) -> dict:
    os_release = parse_os_release(_read_bounded(root / "etc/os-release"))
    dpkg = root / "var/lib/dpkg/status"
    apk = root / "lib/apk/db/installed"
    dpkg_exists, apk_exists = dpkg.is_file(), apk.is_file()
    if os_release == {"id": "void", "version_id": None}:
        if dpkg_exists or apk_exists or not _xbps_registry_absent(root):
            raise InventoryError("Void image retains an unexpected package registry")
        return {
            "schema": "goreecloud.search.runtime-os-registry-unavailable.v1",
            "os": sys.platform,
            "machine": platform.machine(),
            "release": os_release,
            "package_manager": "xbps",
            "package_inventory_status": "unavailable",
            "reason": "runtime_xbps_package_registry_removed",
        }
    if os_release["id"] == "void":
        raise InventoryError("unrecognized Void package registry state")
    if dpkg_exists == apk_exists:
        raise InventoryError("expected exactly one supported OS package database")
    manager = "dpkg" if dpkg_exists else "apk"
    packages = parse_dpkg_status(_read_bounded(dpkg)) if dpkg_exists else parse_apk_installed(_read_bounded(apk))
    return {
        "schema": "goreecloud.search.runtime-os-packages.v1",
        "os": sys.platform,
        "machine": platform.machine(),
        "release": os_release,
        "package_manager": manager,
        "packages": packages,
    }


def main() -> int:
    try:
        print(json.dumps(collect(), sort_keys=True, separators=(",", ":")))
    except InventoryError as error:
        # All InventoryError messages are fixed, code-authored diagnostic
        # categories. They never include package data, paths or source text.
        print("OS_PACKAGE_INVENTORY_BLOCKED: " + str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError):
        print("OS_PACKAGE_INVENTORY_BLOCKED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
