#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fetch exact Docker Hub index and architecture-child bytes with bounded I/O.

This is a read-only, anonymous, fail-closed *evidence collector*, not a build,
signature, SBOM, license, vulnerability, deployment, Seal, or Anchor verdict.
It never accepts arbitrary hosts, redirects, credentials, or mutable output
destinations. The two mutable upstream tags are resolved to immutable digests.
The caller must independently vet registry identity and pin build arguments.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from verify_upstream_base_manifest import (
    INDEX_TYPES, MANIFEST_TYPES, MAX_MANIFEST_BYTES, PLATFORM, ManifestEvidenceError,
    _parse, platform_child_descriptor, verify,
)


AUTH_URL = "https://auth.docker.io/token?" + urlencode({
    "service": "registry.docker.io", "scope": "repository:searxng/base:pull",
})
REGISTRY = "https://registry-1.docker.io/v2/searxng/base/manifests/"
TAGS = ("searxng-builder", "searxng")
ACCEPT = ", ".join(sorted(INDEX_TYPES | MANIFEST_TYPES))
MAX_TOKEN_BYTES = 16 * 1024
PER_IO_TIMEOUT = 5.0
TOTAL_BUDGET_SECONDS = 30.0


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ManifestEvidenceError("registry/token redirect refused")


_OPENER = build_opener(_RejectRedirect)


def _fetch(url: str, headers: dict[str, str], deadline: float, budget: int):
    """One fixed-host HTTPS GET, whole-body cap, connection and read deadlines."""
    if not (url == AUTH_URL or url.startswith(REGISTRY)):
        raise ManifestEvidenceError("external registry URL refused")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ManifestEvidenceError("total registry collection deadline exceeded")
    req = Request(url, headers={**headers, "Accept-Encoding": "identity"})
    try:
        with _OPENER.open(req, timeout=min(PER_IO_TIMEOUT, remaining)) as response:
            if response.status != 200:
                raise ManifestEvidenceError("registry returned non-success status")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ManifestEvidenceError("encoded registry bytes refused")
            declared = response.headers.get("Content-Length")
            if declared is not None and (not declared.isdecimal() or int(declared) > budget):
                raise ManifestEvidenceError("registry response exceeds byte budget")
            parts = []
            count = 0
            while True:
                if time.monotonic() >= deadline:
                    raise ManifestEvidenceError("total registry collection deadline exceeded")
                chunk = response.read(min(65536, budget - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > budget:
                    raise ManifestEvidenceError("registry response exceeds byte budget")
                parts.append(chunk)
            if not count:
                raise ManifestEvidenceError("registry response body empty")
            return response.headers, b"".join(parts)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ManifestEvidenceError("registry/token transport unavailable or refused") from exc


def _fetch_manifest(tag_or_digest: str, token: str, deadline: float, fetch):
    if tag_or_digest not in TAGS and not (
            len(tag_or_digest) == 71 and tag_or_digest.startswith("sha256:")
            and all(ch in "0123456789abcdef" for ch in tag_or_digest[7:])):
        raise ManifestEvidenceError("unsupported registry manifest identifier")
    headers, raw = fetch(REGISTRY + tag_or_digest,
                         {"Authorization": "Bearer " + token, "Accept": ACCEPT},
                         deadline, MAX_MANIFEST_BYTES)
    reported = headers.get("Docker-Content-Digest")
    actual = "sha256:" + hashlib.sha256(raw).hexdigest()
    if reported != actual:
        raise ManifestEvidenceError("registry digest response header missing or mismatched")
    content_type = headers.get("Content-Type", "").split(";", 1)[0].strip()
    document = _parse(raw)
    if content_type != document["mediaType"]:
        raise ManifestEvidenceError("registry response content type differs from raw manifest")
    return actual, raw


def collect(platform: str = "linux/amd64", *, fetch=_fetch, now=time.monotonic):
    """Return self-contained, verified raw image bytes for both upstream tags."""
    if not isinstance(platform, str) or PLATFORM.fullmatch(platform) is None:
        raise ManifestEvidenceError("target platform is not canonical")
    deadline = now() + TOTAL_BUDGET_SECONDS
    auth_headers, auth_raw = fetch(AUTH_URL, {"Accept": "application/json"},
                                   deadline, MAX_TOKEN_BYTES)
    if auth_headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
        raise ManifestEvidenceError("unrecognized Docker Hub token response")
    try:
        payload = json.loads(auth_raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ManifestEvidenceError("malformed Docker Hub token response") from exc
    token = payload.get("token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not 0 < len(token) <= 8192 or "\n" in token or "\r" in token:
        raise ManifestEvidenceError("anonymous scoped registry token unavailable")
    result = {}
    for tag in TAGS:
        digest, index_raw = _fetch_manifest(tag, token, deadline, fetch)
        child_digest, _, _ = platform_child_descriptor(index_raw, platform)
        actual_child, child_raw = _fetch_manifest(child_digest, token, deadline, fetch)
        if actual_child != child_digest:
            raise ManifestEvidenceError("registry returned unexpected child digest")
        immutable_ref = "docker.io/searxng/base@" + digest
        evidence = verify(immutable_ref, index_raw, child_raw, platform)
        result[tag] = {"raw_index": index_raw, "raw_child": child_raw, "evidence": evidence}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", default="linux/amd64", help="e.g. linux/amd64 or linux/arm64")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="new evidence directory; existing directories are never changed")
    args = parser.parse_args(argv)

    def hard_deadline(signum, frame):
        raise ManifestEvidenceError("registry collection hard wall-clock deadline exceeded")

    try:
        if args.output_dir.exists() or args.output_dir.is_symlink():
            raise ManifestEvidenceError("output directory already exists")
        # socket timeouts alone do not bound a peer that drip-feeds bytes.
        # A SIGALRM watchdog bounds the complete anonymous retrieval on Linux.
        if not hasattr(signal, "setitimer"):
            raise ManifestEvidenceError("required hard wall-clock watchdog unavailable")
        previous_handler = signal.signal(signal.SIGALRM, hard_deadline)
        try:
            signal.setitimer(signal.ITIMER_REAL, TOTAL_BUDGET_SECONDS)
            result = collect(args.platform)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
        # No partial output on registry/validation failure; never overwrite.
        args.output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
        summary = {"schema": "goreecloud.search.upstream-base-collected.v1",
                   "collected_at_utc": datetime.now(timezone.utc).isoformat(),
                   "registry": "registry-1.docker.io/v2/searxng/base",
                   "release_decision": "HOLD_NO_SEAL_OR_ANCHOR_QUALIFICATION",
                   "sources": {}}
        for tag, value in result.items():
            (args.output_dir / (tag + ".index.raw.json")).write_bytes(value["raw_index"])
            (args.output_dir / (tag + ".child.raw.json")).write_bytes(value["raw_child"])
            summary["sources"][tag] = value["evidence"]
        (args.output_dir / "evidence.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (ManifestEvidenceError, FileExistsError, OSError, ValueError):
        parser.exit(2, "UPSTREAM_BASE_REGISTRY_COLLECTION_BLOCKED: no release qualification\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
