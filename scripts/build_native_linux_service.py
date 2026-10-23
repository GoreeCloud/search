#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build an offline, source-pinned, *candidate* native Search Linux service zipapp.

This source-only packaging step does not install, enable, sign, certify, or
deploy a service. It deliberately excludes the legacy runtime and crawler.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

if __package__:
    from .source_baseline_inventory import BaselineError, REPO, REPO_URL, SHA, collect
else:
    from source_baseline_inventory import BaselineError, REPO, REPO_URL, SHA, collect


# Strict allowlist: no crawler, no network fetcher, no provider adapter and no
# legacy SearXNG modules can become dependencies of this service artifact.
SERVICE_FILES = (
    "native_search/__init__.py",
    "native_search/api.py",
    "native_search/index.py",
)
MAX_SOURCE_BYTES = 500_000
MANIFEST_NAME = "goreecloud-native-search-build.json"
ENTRYPOINT = '''# SPDX-License-Identifier: AGPL-3.0-or-later
"""Only the owned, local SQLite index can be served from this artifact."""
import argparse
from pathlib import Path

from native_search.api import run_loopback
from native_search.index import SearchIndex


def main():
    parser = argparse.ArgumentParser(prog="goreecloud-search-native-service")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8789)
    args = parser.parse_args()
    if args.db.is_symlink() or not args.db.is_file():
        parser.error("an existing, non-symlink local index database is required")
    with SearchIndex(args.db) as index:
        run_loopback(index, port=args.port)


if __name__ == "__main__":
    main()
'''


class BundleError(Exception):
    """The narrowly scoped native service artifact cannot be constructed."""


def _archive_entry(name: str, content: bytes) -> tuple[ZipInfo, bytes]:
    entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = ZIP_DEFLATED
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    return entry, content


def build_bundle(repo: Path, expected_sha: str) -> bytes:
    """Produce identical bytes for identical sources under one Python/zlib runtime.

    Caller MUST verify exact clean Git provenance separately with `collect`.
    This pure function intentionally makes offline unit testing possible.
    """
    if not SHA.fullmatch(expected_sha):
        raise BundleError("expected exact 40-character lowercase commit SHA")
    source_hashes: dict[str, str] = {}
    archive_files: list[tuple[str, bytes]] = []
    budget = 0
    for name in SERVICE_FILES:
        path = repo / name
        if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
            raise BundleError("required owned service source missing or symlinked: " + name)
        size = path.stat().st_size
        budget += size
        if size <= 0 or budget > MAX_SOURCE_BYTES:
            raise BundleError("native service source exceeds the bounded packaging budget")
        contents = path.read_bytes()
        if len(contents) != size:
            raise BundleError("native service source changed during packaging")
        source_hashes[name] = sha256(contents).hexdigest()
        archive_files.append((name, contents))

    manifest = {
        "schema": "goreecloud.search.native-linux-service-candidate.v1",
        "repository": REPO_URL,
        "source_commit": expected_sha,
        "source_sha256": source_hashes,
        "mode": "development_loopback_service_only",
        "included_capabilities": ["sqlite_fts5_index", "loopback_http_post_search"],
        "excluded_capabilities": [
            "outbound_crawling", "upstream_search_runtime", "provider_network_requests",
            "public_listeners", "shared_authentication", "native_graphical_interface",
        ],
        "not_evaluated": [
            "artifact_signing_and_supply_chain_attestation",
            "linux_install_upgrade_rollback_and_service_lifecycle",
            "macos_windows_android_ios_ipados_native_targets",
            "gc_ui_native_platform_acceptance",
            "production_security_reliability_and_privacy",
            "nine_integral_platform_systems",
            "seal_and_anchor_qualification",
        ],
    }
    archive_files.extend((
        ("__main__.py", ENTRYPOINT.encode("utf-8")),
        (MANIFEST_NAME, (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")),
    ))
    buffer = BytesIO()
    with ZipFile(buffer, mode="w") as archive:
        for name, content in sorted(archive_files):
            info, payload = _archive_entry(name, content)
            archive.writestr(info, payload)
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True,
                        help="exact verified source commit (40 lowercase hexadecimal digits)")
    parser.add_argument("--output", required=True, type=Path,
                        help="create a NEW .pyz; existing artifacts are never overwritten")
    args = parser.parse_args(argv)
    try:
        # Verify the origin, clean checkout, commit/tree and tracked release
        # inputs before touching the output path. No network is contacted.
        collect(REPO, args.expected_sha)
        if args.output.suffix != ".pyz" or args.output.is_symlink():
            raise BundleError("output must be a new, non-symlink .pyz path")
        artifact = build_bundle(REPO, args.expected_sha)
        # Recheck the source boundary after reading all packaged module bytes;
        # a mid-build checkout modification must not become an accepted source.
        collect(REPO, args.expected_sha)
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(artifact)
        print(json.dumps({
            "status": "candidate_only_not_install_or_anchor_evidence",
            "source_commit": args.expected_sha,
            "artifact_sha256": sha256(artifact).hexdigest(),
            "artifact_bytes": len(artifact),
            "output": str(args.output),
        }, sort_keys=True))
    except (BaselineError, BundleError, FileExistsError, FileNotFoundError,
            PermissionError, OSError) as error:
        parser.exit(2, f"NATIVE_SERVICE_BUNDLE_BLOCKED: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
