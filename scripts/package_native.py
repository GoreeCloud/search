"""Create a reproducible, non-installing native GTK4 development archive.

Packaging is offline and first-party. It never installs, overwrites, enables
external providers or changes a local user's desktop configuration.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import stat
import tarfile
from pathlib import Path

PREFIX = "goreecloud-search-native-dev"
MAX_ARCHIVE_MEMBERS = 16
MAX_MEMBER_BYTES = 2_000_000
SOURCE_PATHS = (
    "goreecloud_search/__init__.py",
    "goreecloud_search/store.py",
    "goreecloud_search/links.py",
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
    if any(len(data) > MAX_MEMBER_BYTES for data in files.values()):
        raise ValueError("Development source component exceeds archive size limit")
    files["MANIFEST.sha256"] = "".join(
        f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n"
        for name in sorted(files)
    ).encode("ascii")
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


def verify_archive(path: Path) -> int:
    """Verify a trusted-format development archive without extracting files.

    This proves internal byte consistency, NOT a publisher signature or
    provenance. All members are checked against a fixed allowlist and size cap.
    """
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("Verification requires an existing regular archive path")
    allowed = {
        "README-DEV.txt", "LICENSE", "MANIFEST.sha256",
        "bin/goreecloud-search-native",
        "share/applications/com.goreecloud.Search.Development.desktop",
        *(("lib/" + source) if source.startswith("goreecloud_search/")
          else source for source in SOURCE_PATHS),
    }
    expected = {f"{PREFIX}/{name}" for name in allowed}
    found: dict[str, bytes] = {}
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            if (len(found) >= MAX_ARCHIVE_MEMBERS or member.name not in expected
                    or member.name in found or not member.isfile()
                    or member.size > MAX_MEMBER_BYTES or member.size < 0
                    or member.uid != 0 or member.gid != 0 or member.mtime != 0):
                raise ValueError("Unexpected or unsafe archive member")
            if member.mode != (0o755 if member.name.endswith("/bin/goreecloud-search-native") else 0o644):
                raise ValueError("Unexpected archive permissions")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Unreadable archive member")
            data = stream.read(MAX_MEMBER_BYTES + 1)
            if len(data) != member.size:
                raise ValueError("Archive member size mismatch")
            found[member.name] = data
    if found.keys() != expected:
        raise ValueError("Archive is missing expected members")
    recorded = found.pop(f"{PREFIX}/MANIFEST.sha256").decode("ascii")
    expected_manifest = "".join(
        f"{hashlib.sha256(found[f'{PREFIX}/{name}']).hexdigest()}  {name}\n"
        for name in sorted(allowed - {"MANIFEST.sha256"})
    )
    if recorded != expected_manifest:
        raise ValueError("Archive SHA-256 manifest mismatch")
    return len(found)

def main() -> int:
    parser = argparse.ArgumentParser(description="Build source-only, no-install GTK4 development archive")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--output", type=Path, help="Create new source-only archive")
    operation.add_argument("--verify", type=Path, help="Read-only archive integrity check")
    args = parser.parse_args()
    try:
        if args.verify is not None:
            count = verify_archive(args.verify)
            print(f"Native archive SHA-256 checks passed: {count} source entries (unsigned)")
        else:
            build_archive(args.root.resolve(strict=True), args.output)
            print(f"Native development archive built: {args.output}")
    except (OSError, ValueError, UnicodeError, tarfile.TarError) as exc:
        parser.error(f"Archive operation refused: {exc}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
