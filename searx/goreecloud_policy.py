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


def validate_private_request_context(
    *, host: str, scheme: str, method: str,
    origin: str | None, fetch_site: str | None,
    allowed_public_host: str | None = None,
) -> None:
    """Reject DNS-rebinding hosts and browser cross-site POSTs in the loopback profile.

    Host checks apply to every app route; origin checks apply to state-changing
    requests. Non-browser local clients may omit Origin and Sec-Fetch-Site.
    """
    from urllib.parse import urlsplit

    # An explicitly configured VPS hostname may be accepted only behind the
    # separate VPN-only TLS reverse proxy. Local mode remains loopback-only.
    vps_host_allowed = allowed_public_host == 'search-dev.goreecloud.com' and host == allowed_public_host
    try:
        target = urlsplit('http://' + host)
        valid_host = (
            target.netloc == host
            and (target.hostname in ('127.0.0.1', 'localhost', '::1') or (vps_host_allowed and target.port is None))
            and target.username is None and target.password is None
            and not target.path and not target.query and not target.fragment
            and target.port != 0
        )
    except (TypeError, ValueError):
        valid_host = False
    if not valid_host:
        raise SearchPolicyViolation('Private Search accepts only local Host headers.', 403)

    if method.upper() not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return
    if fetch_site is not None and fetch_site.lower() not in ('same-origin', 'none'):
        raise SearchPolicyViolation('Cross-site private Search requests are disabled.', 403)
    # Chromium can emit an opaque Origin during a genuine local form submit.
    # Accept only when its browser-controlled Fetch Metadata explicitly confirms
    # same-origin; a bare Origin:null or cross-site submission stays blocked.
    if origin == 'null' and fetch_site is not None and fetch_site.lower() == 'same-origin':
        return
    if origin is not None:
        try:
            source = urlsplit(origin)
            same_origin = (
                (source.scheme.lower() == 'https' if vps_host_allowed else source.scheme.lower() == scheme.lower())
                and source.netloc.lower() == host.lower()
                and (source.hostname in ('127.0.0.1', 'localhost', '::1') or vps_host_allowed)
                and source.username is None and source.password is None
                and not source.path and not source.query and not source.fragment
            )
        except (TypeError, ValueError):
            same_origin = False
        if not same_origin:
            raise SearchPolicyViolation('Cross-origin private Search requests are disabled.', 403)


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
    if not isinstance(query, str) or any(category(ch) == 'Cs' for ch in query):
        raise SearchPolicyViolation("Invalid search query encoding.", 422)
    if max_query_chars and len(query) > max_query_chars:
        raise SearchPolicyViolation("Search query exceeds the configured length limit.", 413)
    return len(distinct_selected_sources(provider_names, max_providers=max_providers))


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


def distinct_selected_sources(provider_names: Iterable[str], *, max_providers: int = 0) -> list[str]:
    """Canonical display/count for provider choices, matching fanout policy.

    Retains the first label for case-insensitive duplicates, and sorts the
    resulting labels predictably. It does not imply a successful provider call.
    """
    if isinstance(provider_names, (str, bytes)) or provider_names is None:
        raise SearchPolicyViolation('Invalid search source selection.', 422)
    try:
        names = iter(provider_names)
    except TypeError:
        raise SearchPolicyViolation('Invalid search source selection.', 422) from None
    first_labels: dict[str, str] = {}
    for name in names:
        # Reject malformed labels before scheduling provider network disclosure.
        if (not isinstance(name, str) or not name or len(name) > 128
                or name != name.strip() or any(category(c) in ('Cc', 'Cf', 'Cs', 'Zl', 'Zp') for c in name)):
            raise SearchPolicyViolation('Invalid search source selection.', 422)
        first_labels.setdefault(name.casefold(), name)
        if max_providers and len(first_labels) > max_providers:
            raise SearchPolicyViolation(
                "Too many sources for this search. Select fewer categories or engines.", 422
            )
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
        ch.isspace() or ord(ch) <= 32 or ord(ch) == 127 or category(ch) in ('Cc', 'Cf', 'Cs', 'Zl', 'Zp')
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


def safe_external_media_url(url: object) -> bool:
    """Reject unsafe external HTTPS targets before any private provider fetch.

    DNS rebinding requires a separate network/firewall defense. Validation
    blocks direct local/metadata and malformed-authority SSRF paths only.
    """
    import ipaddress
    import re
    from urllib.parse import urlsplit

    if (not isinstance(url, str) or not url or len(url) > 4096
            or '\\' in url or any(ord(ch) <= 32 or ord(ch) == 127 for ch in url)):
        return False
    try:
        target = urlsplit(url)
        host = target.hostname
        port = target.port
        if (target.scheme.lower() != 'https' or not host
                or port not in (None, 443)
                or target.username is not None or target.password is not None
                or target.fragment or '%' in target.netloc):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        ascii_host = host.encode('idna').decode('ascii').lower()
        if (ascii_host.endswith('.') or len(ascii_host) > 253
                or '.' not in ascii_host or ascii_host.startswith('.')):
            return False
        labels = ascii_host.split('.')
        if any(
            not 1 <= len(label) <= 63
            or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', label)
            for label in labels
        ):
            return False
        if labels[-1] in ('local', 'localhost', 'internal', 'lan', 'invalid',
                          'test', 'example', 'onion', 'arpa'):
            return False
        if not re.fullmatch(r'[a-z]{2,63}|xn--[a-z0-9-]+', labels[-1]):
            return False
        return True
    except (UnicodeError, TypeError, ValueError):
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


# Private-profile approved engine registry. Other SearXNG adapters remain blocked.
SEARCH_SOURCE_FAMILIES = {
    'general': {'brave': 'brave', 'startpage': 'startpage', 'qwant': 'qwant',
                'duckduckgo': 'duckduckgo', 'ecosia': 'ecosia', 'bing': 'bing', 'google': 'google'},
    'images': {'brave': 'brave.images', 'startpage': 'startpage images', 'qwant': 'qwant images',
               'duckduckgo': 'duckduckgo images', 'bing': 'bing images', 'google': 'google images'},
    'videos': {'brave': 'brave.videos', 'qwant': 'qwant videos', 'duckduckgo': 'duckduckgo videos',
               'bing': 'bing videos', 'google': 'google videos'},
    'news': {'brave': 'brave.news', 'startpage': 'startpage news', 'qwant': 'qwant news',
             'duckduckgo': 'duckduckgo news', 'bing': 'bing news', 'google': 'google news'},
}
BUILTIN_SEARCH_SOURCES = frozenset(
    adapter for category in SEARCH_SOURCE_FAMILIES.values() for adapter in category.values()
)
SEARCH_CATEGORIES = tuple(SEARCH_SOURCE_FAMILIES)
SEARCH_SOURCE_COOKIE = 'goreecloud_search_sources'
SEARCH_SOURCE_OPTIONS = {
    'all': ','.join(SEARCH_SOURCE_FAMILIES['general']),
    'both': ','.join(SEARCH_SOURCE_FAMILIES['general']),  # legacy cookie
    **{family: family for family in SEARCH_SOURCE_FAMILIES['general']},
}


def selected_engines_for_category(category: str, choice: str = 'all') -> str:
    """Map saved provider families to actual allowed per-category adapter names.

    No engine fallback is performed: a Startpage-only video request is
    rejected as unsupported, never silently routed to Brave.
    """
    if category not in SEARCH_SOURCE_FAMILIES:
        raise SearchPolicyViolation('That search category is unavailable.', 422)
    available = SEARCH_SOURCE_FAMILIES[category]
    # All Sources selects available per-category engines, never substitutes an
    # unsupported adapter for an explicitly requested single-source category.
    wanted = tuple(available) if choice in ('all', 'both') else (choice,)
    if any(family not in available for family in wanted):
        raise SearchPolicyViolation('The selected search provider does not support this category.', 422)
    return ','.join(available[family] for family in wanted)


def stored_search_source(raw: str | None) -> str:
    """Migrate legacy multi-source cookies and default to All Sources."""
    return raw if raw in SEARCH_SOURCE_OPTIONS and raw != 'both' else 'all'


def requested_search_source(*, explicit: str | None, stored: str | None, query_specific: bool,
                            category: str = 'general') -> str | None:
    """Explicit POST selections and supported !bangs supersede saved preferences.

    A missing cookie preserves SearXNG defaults; no additional data collection
    or silent provider failover is performed.
    """
    if explicit is not None:
        return explicit
    if query_specific or stored is None:
        return None
    return selected_engines_for_category(category, stored_search_source(stored))



def validate_builtin_sources(provider_names: Iterable[str], *, submitted_engines: str | None = None) -> int:
    """Fail closed before a private search/preview can dispatch to any other engine.

    SearXNG normally ignores unrecognized `engines=` entries and falls back to
    default sources. Reject such requests rather than silently broadening egress.
    """
    if submitted_engines is not None:
        supplied = [name.strip() for name in submitted_engines.split(',')]
        if not supplied or any(name not in BUILTIN_SEARCH_SOURCES for name in supplied):
            raise SearchPolicyViolation('Only approved GoreeCloud Search sources are available.', 422)
    names = list(provider_names)
    if not names or any(not isinstance(name, str) or name not in BUILTIN_SEARCH_SOURCES for name in names):
        raise SearchPolicyViolation('Only approved GoreeCloud Search sources are available.', 422)
    return len(set(names))


ALLOWED_SEARCH_BANGS = frozenset({'brave', 'br', 'startpage', 'sp', 'qwant', 'qw', 'duckduckgo', 'ddg', 'ecosia', 'eco', 'bing', 'bi', 'google', 'go', 'general', 'web'})


def validate_builtin_search_bangs(raw_query: str) -> None:
    """Disallow unsupported `!provider` aliases before SearXNG fallback parsing.

    SearXNG treats unknown bang tokens as ordinary words and then searches the
    default engines. Reject instead of silently searching the wrong providers.
    Users can quote a literal word beginning with `!` to search it normally.
    """
    for token in raw_query.split():
        if token.startswith('!'):
            if token.startswith('!!') or token[1:].lower().replace('-', ' ').replace('_', ' ') not in ALLOWED_SEARCH_BANGS:
                raise SearchPolicyViolation('Only approved GoreeCloud Search shortcuts are supported.', 422)


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
