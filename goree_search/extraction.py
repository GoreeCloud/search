"""HTML document extraction with robots noindex exclusion."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlsplit

import trafilatura

from .security import normalize_url


def excludes_index(meta: list[str], x_robots: str = "") -> bool:
    values = ",".join(meta + [x_robots]).lower()
    return any(term.strip().split(":")[-1].strip() in {"noindex", "none"}
               for term in values.replace(";", ",").split(","))


def extract_document(
    html: str, url: str, title: str = "", description: str = ""
) -> dict[str, str] | None:
    body = trafilatura.extract(
        html, output_format="txt", include_comments=False,
        include_tables=True, deduplicate=True,
    )
    if not body or len(body.strip()) < 80:
        return None
    canonical = normalize_url(url)
    clean = body.strip()[:200_000]
    return {
        "url": canonical,
        "host": urlsplit(canonical).hostname or "",
        "title": title.strip()[:240] or canonical,
        "description": description.strip()[:500] or clean[:300],
        "body": clean,
        "language": "und",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
    }
