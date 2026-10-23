#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Verify an offline registry-manifest digest and, for an index, one platform child.

Input must be the *raw response bytes* from an authenticated/trusted registry
manifest retrieval, not a re-serialized JSON printout. This verifies digest
and descriptor consistency only. It cannot attest registry origin, who built
the layers, installed software, image signatures, or release readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


BASE_REF = re.compile(r"docker\.io/searxng/base@sha256:([0-9a-f]{64})\Z")
PLATFORM = re.compile(r"([a-z0-9]+)/([a-z0-9_]+)(?:/([a-z0-9_.-]+))?\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
OCI_INDEX = "application/vnd.oci.image.index.v1+json"
DOCKER_INDEX = "application/vnd.docker.distribution.manifest.list.v2+json"
OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
DOCKER_MANIFEST = "application/vnd.docker.distribution.manifest.v2+json"
INDEX_TYPES = frozenset((OCI_INDEX, DOCKER_INDEX))
MANIFEST_TYPES = frozenset((OCI_MANIFEST, DOCKER_MANIFEST))
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_DESCRIPTORS = 512


class ManifestEvidenceError(ValueError):
    """A raw registry object does not establish the requested digest chain."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestEvidenceError("duplicate JSON member in registry manifest")
        result[key] = value
    return result


def _parse(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_MANIFEST_BYTES:
        raise ManifestEvidenceError("missing or over-budget raw manifest bytes")
    try:
        item = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ManifestEvidenceError("malformed registry manifest JSON") from exc
    if not isinstance(item, dict) or type(item.get("schemaVersion")) is not int or item["schemaVersion"] != 2:
        raise ManifestEvidenceError("expected version-2 registry manifest object")
    if item.get("mediaType") not in INDEX_TYPES | MANIFEST_TYPES:
        raise ManifestEvidenceError("unsupported registry manifest media type")
    return item


def _descriptor(item: object, allowed: frozenset[str]) -> tuple[str, int]:
    if not isinstance(item, dict) or item.get("mediaType") not in allowed:
        raise ManifestEvidenceError("invalid descriptor media type")
    digest, size = item.get("digest"), item.get("size")
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise ManifestEvidenceError("missing or malformed descriptor digest")
    if type(size) is not int or not 0 < size <= 1 << 40:
        raise ManifestEvidenceError("missing or invalid descriptor size")
    if "urls" in item:
        raise ManifestEvidenceError("external descriptor URLs cannot establish a local closure")
    return digest, size


def _manifest(item: dict) -> int:
    _descriptor(item.get("config"), frozenset((
        "application/vnd.oci.image.config.v1+json",
        "application/vnd.docker.container.image.v1+json",
    )))
    layers = item.get("layers")
    if not isinstance(layers, list) or not 0 < len(layers) <= MAX_DESCRIPTORS:
        raise ManifestEvidenceError("manifest layers are absent or unbounded")
    layer_types = frozenset((
        "application/vnd.oci.image.layer.v1.tar",
        "application/vnd.oci.image.layer.v1.tar+gzip",
        "application/vnd.oci.image.layer.v1.tar+zstd",
        "application/vnd.docker.image.rootfs.diff.tar.gzip",
        "application/vnd.docker.image.rootfs.foreign.diff.tar.gzip",
    ))
    for layer in layers:
        _descriptor(layer, layer_types)
    return len(layers)


def verify(base_ref: str, root_raw: bytes, child_raw: bytes | None, platform: str) -> dict:
    """Check cryptographic bytes-to-descriptor links; never return a release PASS."""
    ref = BASE_REF.fullmatch(base_ref)
    target = PLATFORM.fullmatch(platform)
    if ref is None or target is None:
        raise ManifestEvidenceError("base ref or target platform is not canonical")
    if not isinstance(root_raw, bytes) or not 0 < len(root_raw) <= MAX_MANIFEST_BYTES:
        raise ManifestEvidenceError("missing or over-budget raw manifest bytes")
    digest = "sha256:" + hashlib.sha256(root_raw).hexdigest()
    if digest != "sha256:" + ref.group(1):
        raise ManifestEvidenceError("raw top-level manifest bytes do not match requested digest")
    root = _parse(root_raw)
    root_type = root["mediaType"]
    image, child_digest = root, None
    descriptor_count = 0
    if root_type in INDEX_TYPES:
        entries = root.get("manifests")
        if not isinstance(entries, list) or not 0 < len(entries) <= MAX_DESCRIPTORS:
            raise ManifestEvidenceError("index descriptors absent or unbounded")
        descriptor_count = len(entries)
        matches = []
        for desc in entries:
            desc_digest, size = _descriptor(desc, MANIFEST_TYPES)
            p = desc.get("platform")
            if not isinstance(p, dict):
                raise ManifestEvidenceError("index descriptor has no platform")
            if (p.get("os"), p.get("architecture"), p.get("variant")) == target.groups():
                matches.append((desc_digest, size, desc["mediaType"]))
        if len(matches) != 1 or child_raw is None:
            raise ManifestEvidenceError("missing or ambiguous platform manifest child")
        child_digest, size, media_type = matches[0]
        if len(child_raw) != size or "sha256:" + hashlib.sha256(child_raw).hexdigest() != child_digest:
            raise ManifestEvidenceError("platform child bytes do not match index descriptor")
        image = _parse(child_raw)
        if image["mediaType"] != media_type:
            raise ManifestEvidenceError("platform child media type differs from descriptor")
    elif child_raw is not None:
        raise ManifestEvidenceError("unexpected child manifest for top-level image manifest")
    layer_count = _manifest(image)
    return {
        "schema": "goreecloud.search.upstream-base-manifest-evidence.v1",
        "requested_ref": base_ref,
        "requested_platform": platform,
        "root_media_type": root_type,
        "verified_root_manifest_digest": digest,
        "verified_platform_child_digest": child_digest,
        "index_descriptor_count": descriptor_count,
        "image_layer_descriptor_count": layer_count,
        "platform_binding": "index_child_digest_and_platform" if child_digest else "NOT_VERIFIED_DIRECT_MANIFEST",
        "release_decision": "HOLD_NO_SEAL_OR_ANCHOR_QUALIFICATION",
        "not_evaluated": [
            "trusted_registry_origin_or_upstream_identity",
            "actual_docker_pull_or_build_layer_use",
            "content_of_config_or_layers_and_full_sbom",
            "vulnerabilities_licenses_or_signatures",
            "reproducible_build_or_native_platform_runtime_acceptance",
        ],
    }


def _read_raw(path: Path) -> bytes:
    # Enforce the manifest budget before retaining untrusted registry bytes.
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if not 0 < len(raw) <= MAX_MANIFEST_BYTES:
        raise ManifestEvidenceError("raw manifest file is missing or over budget")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True,
                        help="immutable docker.io/searxng/base@sha256:<64-lowercase-hex>")
    parser.add_argument("--root-raw", required=True, type=Path,
                        help="exact raw registry index or image manifest bytes")
    parser.add_argument("--platform", required=True, help="OS/architecture[/variant], e.g. linux/amd64")
    parser.add_argument("--child-raw", type=Path,
                        help="exact raw platform image manifest, required for an index")
    parser.add_argument("--output", type=Path, help="new JSON evidence path; never overwrites")
    args = parser.parse_args(argv)
    try:
        result = verify(args.base_ref, _read_raw(args.root_raw),
                        _read_raw(args.child_raw) if args.child_raw else None, args.platform)
        evidence = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as dest:
                dest.write(evidence)
        else:
            print(evidence, end="")
    except (ManifestEvidenceError, OSError, ValueError):
        parser.exit(2, "UPSTREAM_BASE_MANIFEST_EVIDENCE_BLOCKED: digest/descriptor chain not verified\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
