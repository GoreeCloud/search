#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Hash a bounded selection of runtime ELF-magic files from an isolated image.

This is an unsigned *file-content observation*, not a package-manager database,
complete binary closure, vulnerability scan, license inventory or SBOM. Only
fixed system executable and direct shared-library directories are examined.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys


ELF_MAGIC = b"\x7fELF"
MAX_ENTRIES_PER_DIRECTORY = 5000
MAX_FILES = 1200
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9+_.-]{0,179}\Z")
OS_BINARY = re.compile(r"(?:busybox|python(?:3(?:\.\d+)?)?|wget|curl|openssl)\Z")
OS_LIBRARY = re.compile(
    r"(?:lib[A-Za-z0-9+_.-]+\.so(?:\.[A-Za-z0-9+_.-]+)?|"
    r"ld-[A-Za-z0-9+_.-]+\.so(?:\.[A-Za-z0-9+_.-]+)?)\Z"
)
DIRECTORIES = (("usr/bin", OS_BINARY), ("usr/lib", OS_LIBRARY))


class BinaryInventoryBlocked(Exception):
    """A bounded and privacy-safe observation cannot be completed."""


def _directory(root: Path, relative: str) -> Path:
    path = root
    if root.is_symlink():
        raise BinaryInventoryBlocked("image root cannot be a symlink")
    for component in relative.split("/"):
        path = path / component
        if path.is_symlink():
            raise BinaryInventoryBlocked("system file directory cannot be a symlink")
    if not path.is_dir():
        raise BinaryInventoryBlocked("required system file directory is missing")
    return path


def _hash_regular_elf(path: Path) -> tuple[int, str] | None:
    # Never follow a candidate symlink, even if it points back into the image.
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise BinaryInventoryBlocked("candidate is not a regular file")
        if not 0 < info.st_size <= MAX_FILE_BYTES:
            raise BinaryInventoryBlocked("candidate exceeds bounded size")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = None
            magic = stream.read(4)
            if magic != ELF_MAGIC:
                return None  # Linker scripts are not ELF binaries.
            digest = hashlib.sha256()
            digest.update(magic)
            seen = len(magic)
            while True:
                chunk = stream.read(CHUNK_BYTES)
                if not chunk:
                    break
                seen += len(chunk)
                if seen > MAX_FILE_BYTES:
                    raise BinaryInventoryBlocked("candidate grew beyond bounded size")
                digest.update(chunk)
        if seen != info.st_size:
            raise BinaryInventoryBlocked("candidate changed during observation")
        return seen, digest.hexdigest()
    except (OSError, ValueError):
        raise BinaryInventoryBlocked("runtime file is unreadable or changed") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def collect(root: Path = Path("/")) -> dict:
    """Return only deterministic selected OS-level ELF-magic file hashes."""
    records: list[dict[str, str | int]] = []
    total_bytes = 0
    for relative, matcher in DIRECTORIES:
        directory = _directory(root, relative)
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError:
            raise BinaryInventoryBlocked("runtime directory is unreadable") from None
        if len(entries) > MAX_ENTRIES_PER_DIRECTORY:
            raise BinaryInventoryBlocked("runtime directory exceeds entry budget")
        for candidate in entries:
            if not FILE_NAME.fullmatch(candidate.name) or not matcher.fullmatch(candidate.name):
                continue
            if candidate.is_symlink():
                continue
            result = _hash_regular_elf(candidate)
            if result is None:
                continue
            size, digest = result
            records.append({"path": "/" + relative + "/" + candidate.name,
                            "size_bytes": size, "sha256": digest})
            total_bytes += size
            if len(records) > MAX_FILES or total_bytes > MAX_TOTAL_BYTES:
                raise BinaryInventoryBlocked("selected runtime files exceed observation budget")
    records.sort(key=lambda item: str(item["path"]))
    if not any(row["path"] == "/usr/bin/busybox" for row in records):
        raise BinaryInventoryBlocked("expected core OS executable is missing")
    if not any(str(row["path"]).startswith("/usr/lib/") for row in records):
        raise BinaryInventoryBlocked("no selected runtime shared libraries found")
    return {
        "schema": "goreecloud.search.runtime-selected-elf-hashes.v1",
        "os": sys.platform,
        "machine": platform.machine(),
        "selection": "regular_elf_magic_usr_bin_tools_and_direct_usr_lib_shared_libraries_v1",
        "files": records,
        "total_bytes_hashed": total_bytes,
    }


def main() -> int:
    try:
        print(json.dumps(collect(), sort_keys=True, separators=(",", ":")))
    except (BinaryInventoryBlocked, OSError, ValueError, TypeError):
        print("RUNTIME_BINARY_OBSERVATION_BLOCKED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
