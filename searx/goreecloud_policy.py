# SPDX-License-Identifier: AGPL-3.0-or-later
"""GoreeCloud Search privacy limits, applied before network dispatch.

This module deliberately has no Flask, logging or provider-transport dependency.
It never stores, emits or normalizes the user's raw search terms.
"""

from __future__ import annotations

from collections.abc import Iterable
from unicodedata import category


class SearchPolicyViolation(ValueError):
    """A query was rejected before it could reach an external provider."""

    def __init__(self, message: str, http_status: int):
        super().__init__(message)
        self.http_status = http_status


def validate_transport(*, method: str, query_in_url: bool, private: bool) -> None:
    """Reject query-bearing GET requests and all URL query parameters in private mode."""
    if private and (query_in_url or method.upper() != "POST"):
        raise SearchPolicyViolation(
            "Private searches must use POST without query parameters in the URL.", 405
        )


def validate_disclosure(
    query: str,
    provider_names: Iterable[str],
    *,
    max_query_chars: int,
    max_providers: int,
) -> int:
    """Bound query size and unique provider fanout without silently truncating results.

    All checks happen *before* constructing a provider execution object.
    A zero limit means no maximum; negative settings are always invalid.
    """
    if max_query_chars < 0 or max_providers < 0:
        raise ValueError("Privacy limits must be non-negative")
    if max_query_chars and len(query) > max_query_chars:
        raise SearchPolicyViolation("Search query exceeds the configured length limit.", 413)
    unique = distinct_selected_sources(provider_names)
    if max_providers and len(unique) > max_providers:
        raise SearchPolicyViolation(
            "Too many sources for this search. Select fewer categories or engines.", 422
        )
    return len(unique)


def validate_no_external_redirects(*, external_bang: str | None, lucky_redirect: bool) -> None:
    """Keep privately submitted searches on GoreeCloud's result page.

    External bangs and '!!' direct-result navigation otherwise turn a private
    search POST into a browser navigation with terms in a third-party URL.
    Ordinary engine/category bangs remain supported.
    """
    if external_bang or lucky_redirect:
        raise SearchPolicyViolation(
            "Direct external search redirects are disabled in private mode. Remove external bangs or !!.",
            422,
        )


def distinct_selected_sources(provider_names: Iterable[str]) -> list[str]:
    """Canonical display/count for provider choices, matching fanout policy.

    Retains the first label for case-insensitive duplicates, and sorts the
    resulting labels predictably. It does not imply a successful provider call.
    """
    first_labels: dict[str, str] = {}
    for name in provider_names:
        # Reject malformed labels before scheduling provider network disclosure.
        if (not isinstance(name, str) or not name or len(name) > 128
                or name != name.strip() or any(category(c) in ('Cc', 'Cf', 'Zl', 'Zp') for c in name)):
            raise SearchPolicyViolation('Invalid search source selection.', 422)
        first_labels.setdefault(name.casefold(), name)
    return sorted(first_labels.values(), key=lambda label: (label.casefold(), label))


def safe_primary_result_url(url: object) -> bool:
    """Allow only unambiguous HTTP(S) top-level result destinations.

    Protects the private consumer from executable URL schemes and malformed
    authority syntax. This is *not* a general-purpose provider SSRF filter:
    it governs user-visible result links only.
    """
    from urllib.parse import urlsplit
    from unicodedata import category

    if not isinstance(url, str) or not url or any(
        ord(ch) <= 32 or ord(ch) == 127 or category(ch) in ('Cc', 'Cf', 'Zl', 'Zp')
        for ch in url
    ):
        return False
    if '\\' in url:
        return False
    try:
        parsed = urlsplit(url)
        # Accessing .port validates its numeric grammar and 0..65535 range.
        # .hostname alone accepts malformed ports such as :abc or :99999.
        port = parsed.port
        return (
            (port is None or port > 0)
            and parsed.scheme.lower() in ('http', 'https')
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and '%' not in parsed.hostname
        )
    except ValueError:
        return False


def represented_result_sources(results: Iterable[object], selected_names: Iterable[str]) -> dict[str, int]:
    """Count selected provider labels attached to *displayed* primary results.

    Multiple selected engines can label a single aggregated result. Counts are
    therefore overlapping result attributions, not network request counts,
    response confirmations, or independent evidence of provider authenticity.
    Only names in the query's selected set appear in the output.
    """
    selected = {label.casefold(): label for label in distinct_selected_sources(selected_names)}
    counts: dict[str, int] = {}
    for result in results:
        raw = getattr(result, 'engines', None)
        if isinstance(raw, str):
            names = [raw]
        elif isinstance(raw, (list, tuple, set, frozenset)):
            names = list(raw)
        else:
            names = []
        engine = getattr(result, 'engine', None)
        if isinstance(engine, str):
            names.append(engine)
        matched = {
            selected[name.casefold()] for name in names
            if isinstance(name, str) and name.casefold() in selected
        }
        for name in matched:
            counts[name] = counts.get(name, 0) + 1
    return {name: counts[name] for name in sorted(counts, key=lambda label: (label.casefold(), label))}


# Product-wide private Search provider allowlist; legacy upstream adapters
# remain in the upstream source tree but are not selectable or executable.
BUILTIN_SEARCH_SOURCES = frozenset({'brave', 'startpage'})


def validate_builtin_sources(provider_names: Iterable[str], *, submitted_engines: str | None = None) -> int:
    """Fail closed before a private search/preview can dispatch to any other engine.

    SearXNG normally ignores unrecognized `engines=` entries and falls back to
    default sources. Reject such requests rather than silently broadening egress.
    """
    if submitted_engines is not None:
        supplied = [name.strip() for name in submitted_engines.split(',')]
        if not supplied or any(name not in BUILTIN_SEARCH_SOURCES for name in supplied):
            raise SearchPolicyViolation('Only Brave Search and Startpage are available.', 422)
    names = list(provider_names)
    if not names or any(not isinstance(name, str) or name not in BUILTIN_SEARCH_SOURCES for name in names):
        raise SearchPolicyViolation('Only Brave Search and Startpage are available.', 422)
    return len(set(names))


ALLOWED_SEARCH_BANGS = frozenset({'brave', 'br', 'startpage', 'sp', 'general', 'web'})


def validate_builtin_search_bangs(raw_query: str) -> None:
    """Disallow unsupported `!provider` aliases before SearXNG fallback parsing.

    SearXNG treats unknown bang tokens as ordinary words and then searches the
    default engines. Reject instead of silently searching the wrong providers.
    Users can quote a literal word beginning with `!` to search it normally.
    """
    for token in raw_query.split():
        if token.startswith('!'):
            if token.startswith('!!') or token[1:].lower().replace('-', ' ').replace('_', ' ') not in ALLOWED_SEARCH_BANGS:
                raise SearchPolicyViolation('Only Brave Search and Startpage search shortcuts are supported.', 422)


def restrict_explicit_private_engines(enginerefs: Iterable[object], selected: str | None) -> list[object]:
    """Honor the explicit approved selection even if a category also appears."""
    refs = list(enginerefs)
    validate_builtin_sources((ref.name for ref in refs), submitted_engines=selected)
    if selected is None:
        return refs
    requested = {name.strip() for name in selected.split(',')}
    result = [ref for ref in refs if ref.name in requested]
    if {ref.name for ref in result} != requested:
        raise SearchPolicyViolation('The selected search source is unavailable for this query.', 422)
    return result
