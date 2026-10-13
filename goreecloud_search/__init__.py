"""Offline, provider-neutral result fusion for GoreeCloud Search Development.

This module never performs a network request or stores query/client identity.
Provider adapters may supply results only after separate privacy authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import re

MAX_ENGINES = 16
MAX_RESULTS_PER_ENGINE = 50
MAX_URL_CHARS = 2048
TRACKING_KEYS = frozenset({"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid"})
ENGINE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    engines: tuple[str, ...]
    score: float

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "engines": list(self.engines),
            "score": round(self.score, 8),
        }


def canonical_result_url(raw: str) -> str | None:
    """Return a display-safe HTTP(S) URL stripped of common tracking fields."""
    if not isinstance(raw, str) or not raw or len(raw) > MAX_URL_CHARS:
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 or ch.isspace() or ch == "\\" for ch in raw):
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in {"http", "https"}:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        host = parsed.hostname
        port = parsed.port
        if not host or host.endswith(".") or any(c in host for c in "/\\@"):
            return None
        if host.casefold() == "localhost":
            return None
        host = host.casefold()
        authority = f"[{host}]" if ":" in host else host
        if port is not None:
            if port < 1 or port > 65535:
                return None
            if not (parsed.scheme.lower() == "http" and port == 80 or
                    parsed.scheme.lower() == "https" and port == 443):
                authority = f"{authority}:{port}"
        params = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=100)
        kept = [(key, value) for key, value in params
                if not key.casefold().startswith("utm_") and key.casefold() not in TRACKING_KEYS]
        query = urlencode(kept)
        return urlunsplit((parsed.scheme.lower(), authority, parsed.path or "/", query, ""))
    except (ValueError, UnicodeError):
        return None


def fuse_results(
    sources: Mapping[str, Sequence[Mapping[str, str]]],
    *,
    limit: int = 10,
) -> tuple[SearchHit, ...]:
    """Reciprocal-rank fusion with deterministic canonical-URL deduplication.

    Expected input: {engine_id: [{title, url, snippet}, ...]}. Engine names
    are stable identifiers, not user credentials. This function neither
    fetches content nor handles live query text.
    """
    if not isinstance(sources, Mapping) or len(sources) > MAX_ENGINES:
        raise ValueError("invalid_search_sources")
    if any(not isinstance(engine, str) or not ENGINE_ID.fullmatch(engine) for engine in sources):
        raise ValueError("invalid_search_engine_id")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("invalid_search_result_limit")

    merged: dict[str, dict] = {}
    for engine in sorted(sources):
        rows = sources[engine]
        if not isinstance(engine, str) or not ENGINE_ID.fullmatch(engine):
            raise ValueError("invalid_search_engine_id")
        if not isinstance(rows, (list, tuple)) or len(rows) > MAX_RESULTS_PER_ENGINE:
            raise ValueError("invalid_search_engine_results")
        seen_in_engine: set[str] = set()
        for rank, row in enumerate(rows, 1):
            if not isinstance(row, Mapping):
                raise ValueError("invalid_search_result")
            title, raw_url, snippet = row.get("title"), row.get("url"), row.get("snippet", "")
            if not isinstance(title, str) or not isinstance(snippet, str):
                raise ValueError("invalid_search_result_text")
            if not title.strip() or len(title) > 180 or len(snippet) > 500:
                raise ValueError("invalid_search_result_text")
            url = canonical_result_url(raw_url)
            if url is None or url in seen_in_engine:
                continue
            seen_in_engine.add(url)
            entry = merged.setdefault(url, {
                "title": title.strip(), "snippet": snippet, "engines": [], "score": 0.0,
            })
            entry["engines"].append(engine)
            entry["score"] += 1.0 / (60 + rank)

    ordered = sorted(merged.items(), key=lambda item: (
        -item[1]["score"], -len(item[1]["engines"]), item[0],
    ))
    return tuple(SearchHit(
        title=item["title"], url=url, snippet=item["snippet"],
        engines=tuple(item["engines"]), score=item["score"],
    ) for url, item in ordered[:limit])
