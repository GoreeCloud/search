"""Create a reproducible, non-installing native GTK4 development archive.

Packaging is offline and first-party. It never installs, overwrites, enables
external providers or changes a local user's desktop configuration.
"""
from __future__ import annotations

import argparse
import gzip
import io
import os
import stat
import tarfile
from pathlib import Path

PREFIX = "goreecloud-search-native-dev"
SOURCE_PATHS = (
    "goreecloud_search/__init__.py",
    "goreecloud_search/store.py",
    "goreecloud_search/native.py",
    "LICENSE",
)
LAUNCHER = """#!/usr/bin/env python3
\"\"\"Portable GoreeCloud Search native development launcher.\"\"\"
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "lib"))
from goreecloud_search.native import main

if __name__ == "__main__":
    raise SystemExit(main())
"""
DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Version=1.0
Name=GoreeCloud Search (Development)
Comment=Private local catalog search; no outbound providers
Exec=goreecloud-search-native
Icon=system-search
Terminal=false
Categories=Utility;
StartupNotify=true
"""
README = """GoreeCloud Search — GTK4 development archive (NOT installed or released)

This archive is self-contained first-party Python source but relies on an
operating-system-provided Python 3.11+, SQLite FTS5, PyGObject and GTK4.

Extract to a directory you own. Run bin/goreecloud-search-native --help
to inspect options, or run it with --db PATH pointing at an existing,
privately initialized SQLite FTS5 Search catalog.

A freedesktop .desktop template is included as a DEVELOPMENT REFERENCE;
it requires goreecloud-search-native to be on PATH before desktop launch.
The packaging tool does NOT install it, change PATH, execute installers,
modify desktop settings, or access other network services.

The client searches the local index only. No Brave/SearXNG credentials,
query forwarding, provider activation, telemetry, or automatic updates.
Validate GTK rendering, keyboard, assistive tech, packaging, signing and
OS compatibility before considering production distribution.

Source: https://github.com/GoreeCloud/search
"""

def _source_bytes(root: Path, name: str) -> bytes:
    target = root / name
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid source repository root")
    for parent in (target, *target.parents):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise ValueError(f"Symlinked source path refused: {name}")
    if not target.is_file() or not stat.S_ISREG(target.stat().st_mode):
        raise ValueError(f"Missing regular source file: {name}")
    return target.read_bytes()

def _tar_member(name: str, data: bytes, executable: bool = False) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name=f"{PREFIX}/{name}")
    info.size = len(data)
    info.mode = 0o755 if executable else 0o644
    info.uid = info.gid = info.mtime = 0
    info.uname = info.gname = ""
    return info, data

def archive_members(root: Path) -> list[tuple[tarfile.TarInfo, bytes]]:
    files = {
        "bin/goreecloud-search-native": LAUNCHER.encode("utf-8"),
        "share/applications/com.goreecloud.Search.Development.desktop": DESKTOP_ENTRY.encode("utf-8"),
        "README-DEV.txt": README.encode("utf-8"),
    }
    for source in SOURCE_PATHS:
        destination = "lib/" + source if source.startswith("goreecloud_search/") else source
        files[destination] = _source_bytes(root, source)
    return [
        _tar_member(name, files[name], executable=name.startswith("bin/"))
        for name in sorted(files)
    ]

def build_archive(root: Path, output: Path) -> None:
    # Validate every member before opening/creating the output.
    members = archive_members(root)
    if not output.is_absolute():
        raise ValueError("Output must be an absolute path")
    if output.is_symlink():
        raise ValueError("Symlinked output refused")
    # Exclusive creation protects existing archives (and dangling symlinks).
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as gz:
                with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                    for info, data in members:
                        archive.addfile(info, io.BytesIO(data))
    except BaseException:
        if fd >= 0:
            os.close(fd)
        output.unlink(missing_ok=True)
        raise

def main() -> int:
    parser = argparse.ArgumentParser(description="Build source-only, no-install GTK4 development archive")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_archive(args.root.resolve(strict=True), args.output)
    except (OSError, ValueError, tarfile.TarError) as exc:
        parser.error(f"Archive refused: {exc}")
    print(f"Native development archive built: {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
