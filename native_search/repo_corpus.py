# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local, explicitly approved GoreeCloud repository docs -> native Search index.

Never fetches repositories or URLs. Owner-supplied manifest paths and immutable
commit references make corpus provenance inspectable; all validation precedes
any index write. Not a general site crawler or an automatic GitHub indexer.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote

from .index import SearchIndex

MAX_DOCUMENT_BYTES = 160_000
MAX_TOTAL_BYTES = 1_000_000
MAX_APPROVED_FILES = 50
REPOSITORY = "GoreeCloud/search"
SAFE_DOCS = PurePosixPath("docs/goreecloud")


def load_approved_manifest(path: str | Path) -> list[str]:
    raw = Path(path).read_bytes()
    if len(raw) > 16_384:
        raise ValueError("Corpus approval manifest exceeds limit")
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid corpus approval manifest") from exc
    if (not isinstance(manifest, dict) or set(manifest) != {"repository", "approved_paths"}
            or manifest["repository"] != REPOSITORY
            or not isinstance(manifest["approved_paths"], list)):
        raise ValueError("Expected explicitly approved GoreeCloud repository paths")
    paths = manifest["approved_paths"]
    if not 1 <= len(paths) <= MAX_APPROVED_FILES or len(set(map(str, paths))) != len(paths):
        raise ValueError("Invalid document count or duplicate approvals")
    return paths


def _approved_path(root: Path, name: str) -> tuple[Path, str]:
    if not isinstance(name, str) or len(name) > 160 or not name.isascii():
        raise ValueError("Invalid approved document path")
    p = PurePosixPath(name)
    if (p.is_absolute() or len(p.parts) != 3 or p.parts[:2] != SAFE_DOCS.parts
            or p.suffix != ".md" or not re.fullmatch(r"[A-Za-z0-9_-]+\.md", p.name)
            or str(p) != name):
        raise ValueError("Only directly approved docs/goreecloud/*.md are importable")
    resolved = root
    for segment in p.parts:
        resolved = resolved / segment
        if resolved.is_symlink():
            raise ValueError("Symlinked corpus paths are not approved")
    if not resolved.is_file() or resolved.resolve().parent != (root / "docs/goreecloud").resolve():
        raise ValueError("Missing or unsafe approved repository document")
    return resolved, name


def import_approved_repo_docs(
    index: SearchIndex, repo_root: str | Path, *, revision: str,
    approved_paths: list[str],
) -> dict[str, int]:
    """Offline import of a reviewed manifest, fail-before-write on invalid data."""
    if not isinstance(revision, str) or not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("Use an exact lowercase immutable Git commit SHA")
    root = Path(repo_root).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Repository root must be a real directory")
    if not isinstance(approved_paths, list) or not 1 <= len(approved_paths) <= MAX_APPROVED_FILES:
        raise ValueError("1 to 50 explicit approved document paths required")
    if any(not isinstance(x, str) for x in approved_paths):
        raise ValueError("Invalid approved document entry")
    if len(set(approved_paths)) != len(approved_paths):
        raise ValueError("Duplicate document approval")
    candidate_docs: list[tuple[str, str, str]] = []
    total_bytes = 0
    for name in approved_paths:
        source, rel = _approved_path(root, name)
        data = source.read_bytes()
        total_bytes += len(data)
        if not data or len(data) > MAX_DOCUMENT_BYTES or total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("Approved document exceeds corpus budget")
        try:
            body = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("Corpus document must be UTF-8") from exc
        headings = [line.lstrip("# ").strip() for line in body.splitlines()
                    if line.startswith("# ") and line[2:].strip()]
        if not headings:
            raise ValueError("Approved Markdown document needs a top-level heading")
        title = headings[0][:300]
        url = "https://github.com/" + REPOSITORY + "/blob/" + revision + "/" + quote(rel, safe="/")
        candidate_docs.append((url, title, body))
    # Validates first and commits the full batch in one SQLite transaction.
    index.add_many(candidate_docs)
    return {"imported": len(candidate_docs), "bytes": total_bytes}
