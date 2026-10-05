from __future__ import annotations

import re
from dataclasses import dataclass
from unicodedata import category as unicode_category

from .models import ParsedQuery

DEFAULT_SNIPPET_MAX_CHARS = 280
MAX_SNIPPET_SOURCE_CHARS = 32_768
_MIN_SNIPPET_MAX_CHARS = 80
_WHITESPACE = re.compile(r"\s+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_BIDI_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


class SnippetGenerationError(ValueError):
    """Raised when snippet-generation input violates the bounded contract."""


@dataclass(frozen=True, slots=True)
class GeneratedSnippet:
    """Bounded snippet plus provenance over the normalized source window."""

    text: str
    matched_query: bool
    source_truncated: bool
    start_offset: int
    end_offset: int


def _normalize_source(text: str) -> tuple[str, bool]:
    if not isinstance(text, str):
        raise SnippetGenerationError("snippet source must be text")

    bounded = text[:MAX_SNIPPET_SOURCE_CHARS]
    source_truncated = len(text) > len(bounded)
    sanitized = "".join(
        " "
        if unicode_category(character) == "Cc" or character in _BIDI_CONTROLS
        else character
        for character in bounded
    )
    normalized = _WHITESPACE.sub(" ", sanitized).strip()
    return normalized, source_truncated


def _needles(query: ParsedQuery) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for value in (*query.phrases, *query.terms):
        cleaned = _WHITESPACE.sub(" ", value).strip()
        folded = cleaned.casefold()
        if cleaned and folded not in seen:
            values.append(cleaned)
            seen.add(folded)
    return tuple(values)


def _best_match(text: str, needles: tuple[str, ...]) -> tuple[int, int] | None:
    # Keep spans anchored to the original normalized string. Building offsets
    # from casefolded text is unsafe because Unicode case folding can change
    # string length (for example, some characters expand to multiple code points).
    matches: list[tuple[int, int, int]] = []
    for needle in needles:
        match = re.search(re.escape(needle), text, flags=re.IGNORECASE)
        if match is not None:
            matches.append((match.start(), -len(match.group(0)), match.end()))
    if not matches:
        return None
    start, _, end = min(matches)
    return start, end


def _clip(
    text: str,
    *,
    focus_start: int,
    focus_end: int,
    max_chars: int,
) -> tuple[str, int, int]:
    if len(text) <= max_chars:
        return text, 0, len(text)

    # Reserve room for leading/trailing ellipses before selecting the body window.
    body_budget = max_chars - 2
    focus_mid = (focus_start + focus_end) // 2
    start = max(0, focus_mid - body_budget // 2)
    end = min(len(text), start + body_budget)
    start = max(0, end - body_budget)

    # Avoid starting or ending in the middle of a word when a nearby boundary exists.
    if start > 0:
        boundary = text.find(" ", start, min(start + 24, end))
        if boundary >= 0:
            start = boundary + 1
    if end < len(text):
        boundary = text.rfind(" ", max(start, end - 24), end)
        if boundary > start:
            end = boundary

    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    hard_body_budget = max_chars - len(prefix) - len(suffix)
    body = text[start:end].strip()
    if len(body) > hard_body_budget:
        body = body[:hard_body_budget].rstrip()
        end = start + len(body)
        suffix = "…"
    return f"{prefix}{body}{suffix}", start, end


def generate_snippet(
    query: ParsedQuery,
    source_text: str,
    *,
    max_chars: int = DEFAULT_SNIPPET_MAX_CHARS,
) -> GeneratedSnippet:
    """Generate a deterministic local-only snippet from already-authorized plain text.

    The generator performs no network or filesystem I/O and receives no authority
    to fetch content. Callers must supply text they are already authorized to
    process. Source text is bounded before processing, unsafe display controls are
    removed, and the result retains no full source text. Offsets refer to the
    normalized bounded source used by this function, not the caller's raw input.
    """

    if isinstance(max_chars, bool) or not isinstance(max_chars, int):
        raise SnippetGenerationError("max_chars must be an integer")
    if max_chars < _MIN_SNIPPET_MAX_CHARS:
        raise SnippetGenerationError(
            f"max_chars must be at least {_MIN_SNIPPET_MAX_CHARS}"
        )
    if max_chars > DEFAULT_SNIPPET_MAX_CHARS:
        raise SnippetGenerationError(
            f"max_chars must not exceed {DEFAULT_SNIPPET_MAX_CHARS}"
        )

    text, source_truncated = _normalize_source(source_text)
    if not text:
        return GeneratedSnippet(
            text="",
            matched_query=False,
            source_truncated=source_truncated,
            start_offset=0,
            end_offset=0,
        )

    match = _best_match(text, _needles(query))
    matched_query = match is not None

    if match is None:
        # Prefer a complete leading sentence when it fits; otherwise use the same
        # deterministic bounded clipping path as query-focused snippets.
        first_sentence = _SENTENCE_BREAK.split(text, maxsplit=1)[0]
        suffix = "…" if len(first_sentence) < len(text) else ""
        if first_sentence and len(first_sentence) + len(suffix) <= max_chars:
            end = len(first_sentence)
            return GeneratedSnippet(
                text=f"{first_sentence}{suffix}",
                matched_query=False,
                source_truncated=source_truncated,
                start_offset=0,
                end_offset=end,
            )
        focus_start = 0
        focus_end = min(len(text), max_chars)
    else:
        focus_start, focus_end = match

    snippet, start, end = _clip(
        text,
        focus_start=focus_start,
        focus_end=focus_end,
        max_chars=max_chars,
    )
    return GeneratedSnippet(
        text=snippet,
        matched_query=matched_query,
        source_truncated=source_truncated,
        start_offset=start,
        end_offset=end,
    )
