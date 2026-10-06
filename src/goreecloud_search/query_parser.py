from __future__ import annotations

from datetime import date
import re
import shlex

from .models import ParsedQuery, QueryFilters, SearchCategory


class QueryParseError(ValueError):
    """Raised when a query contains an invalid supported operator."""


_TOKEN_RE = re.compile(r'-?"(?:[^"\\]|\\.)*"|\S+')
_CATEGORY_ALIASES = {
    "code": SearchCategory.SOURCE_CODE,
    "source-code": SearchCategory.SOURCE_CODE,
    "source_code": SearchCategory.SOURCE_CODE,
    "docs": SearchCategory.DOCUMENTATION,
    "documentation": SearchCategory.DOCUMENTATION,
    "map": SearchCategory.MAPS,
    "maps": SearchCategory.MAPS,
    "forum": SearchCategory.FORUMS,
    "forums": SearchCategory.FORUMS,
    "discussion": SearchCategory.DISCUSSIONS,
    "discussions": SearchCategory.DISCUSSIONS,
}


def _tokens(raw: str) -> list[tuple[str, bool]]:
    parsed: list[tuple[str, bool]] = []
    previous_end = 0
    for match in _TOKEN_RE.finditer(raw):
        # Adjacent quoted and unquoted fragments are ambiguous. Require spaces
        # rather than interpreting a malformed operator or phrase differently.
        if match.start() == previous_end and previous_end and not raw[previous_end - 1].isspace():
            raise QueryParseError("separate quoted phrases from other query tokens")
        token = match.group(0)
        negated_phrase = token.startswith('-"') and token.endswith('"')
        quoted = token.startswith('"') and token.endswith('"')
        if quoted or negated_phrase:
            try:
                decoded = shlex.split(token, posix=True)
            except ValueError as exc:
                raise QueryParseError(str(exc)) from exc
            if len(decoded) != 1 or not decoded[0] or (negated_phrase and decoded[0] == "-"):
                raise QueryParseError("invalid quoted phrase")
            token = decoded[0]
        elif '"' in token:
            raise QueryParseError("unbalanced or misplaced quote")
        parsed.append((token, quoted))
        previous_end = match.end()
    return parsed


def _value(token: str, prefix: str) -> str:
    value = token[len(prefix):].strip()
    if not value:
        raise QueryParseError(f"{prefix[:-1]} requires a value")
    return value


def _domain(value: str) -> str:
    normalized = value.strip().lower().rstrip(".")
    if not normalized or any(char.isspace() for char in normalized):
        raise QueryParseError(f"invalid domain: {value!r}")
    return normalized


def _date(value: str, operator: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise QueryParseError(f"{operator} requires an ISO date in YYYY-MM-DD form") from exc


def _category(value: str) -> SearchCategory:
    normalized = value.strip().lower()
    if normalized in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[normalized]
    try:
        return SearchCategory(normalized)
    except ValueError as exc:
        supported = ", ".join(category.value for category in SearchCategory)
        raise QueryParseError(f"unsupported category {value!r}; supported categories: {supported}") from exc


def parse_query(raw: str) -> ParsedQuery:
    """Parse supported query syntax without resolving or dispatching providers."""
    if not raw or not raw.strip():
        raise QueryParseError("query must not be empty")

    terms: list[str] = []
    phrases: list[str] = []
    excluded_terms: list[str] = []
    sites: list[str] = []
    excluded_domains: list[str] = []
    filetypes: list[str] = []
    sources: list[str] = []
    before: date | None = None
    after: date | None = None
    language: str | None = None
    region: str | None = None
    category = SearchCategory.GENERAL
    lens: str | None = None

    for token, quoted in _tokens(raw):
        lower = token.lower()
        if quoted:
            # A quoted operator is literal search text, not an active filter.
            phrases.append(token)
        elif lower.startswith("site:"):
            sites.append(_domain(_value(token, "site:")))
        elif lower.startswith("-domain:"):
            excluded_domains.append(_domain(_value(token, "-domain:")))
        elif lower.startswith("filetype:"):
            filetypes.append(_value(token, "filetype:").lower().lstrip("."))
        elif lower.startswith("ext:"):
            filetypes.append(_value(token, "ext:").lower().lstrip("."))
        elif lower.startswith("before:"):
            before = _date(_value(token, "before:"), "before:")
        elif lower.startswith("after:"):
            after = _date(_value(token, "after:"), "after:")
        elif lower.startswith("language:"):
            language = _value(token, "language:").lower()
        elif lower.startswith("region:"):
            region = _value(token, "region:").upper()
        elif lower.startswith("source:"):
            sources.append(_value(token, "source:").casefold())
        elif lower.startswith("category:"):
            category = _category(_value(token, "category:"))
        elif lower.startswith("lens:"):
            lens = _value(token, "lens:")
        elif token.startswith("-") and len(token) > 1:
            excluded_terms.append(token[1:])
        else:
            terms.append(token)

    if after and before and after > before:
        raise QueryParseError("after: date must be on or before before: date")
    if not terms and not phrases and not sites:
        raise QueryParseError("query must contain a term, quoted phrase, or site: restriction")

    return ParsedQuery(
        raw=raw,
        terms=tuple(terms),
        phrases=tuple(phrases),
        excluded_terms=tuple(excluded_terms),
        filters=QueryFilters(
            sites=tuple(dict.fromkeys(sites)),
            excluded_domains=tuple(dict.fromkeys(excluded_domains)),
            filetypes=tuple(dict.fromkeys(filetypes)),
            before=before,
            after=after,
            language=language,
            region=region,
            sources=tuple(dict.fromkeys(sources)),
            category=category,
            lens=lens,
        ),
    )
