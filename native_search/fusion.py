# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic, offline Search Fusion Engine foundation.

This is a GoreeCloud-owned, provider-neutral *development* module. It does not
make network requests, authorize an upstream license, or join the deployed
SearXNG path. The separate native Linux development candidate packages it.

Only distinct upstream sources earn ranking votes for a duplicate result.
The implementation intentionally uses URL identity, not unverified semantic
similarity, for its first-stage deduplication contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SUPPORTED_CATEGORIES = frozenset({'web', 'images', 'videos', 'news'})
_PROVIDER_ID = re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')
_TRACKING_KEYS = frozenset({'fbclid', 'gclid', 'dclid', 'msclkid', 'igshid', 'mc_cid', 'mc_eid'})
_CONTROL = re.compile(r'[\x00-\x20\x7f\\]')
_QUERY_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
_LEXICAL_WORD = re.compile(r'[^\W_]+', re.UNICODE)
_YOUTUBE_VIDEO_ID = re.compile(r'[A-Za-z0-9_-]{11}\Z')
_YOUTUBE_HOSTS = frozenset({
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com',
    'youtube-nocookie.com', 'www.youtube-nocookie.com',
})
_YOUTU_BE_HOSTS = frozenset({'youtu.be', 'www.youtu.be'})
_MAX_CANDIDATES = 1000
_MAX_QUERY_TERMS = 16


@dataclass(frozen=True)
class SourceResult:
    """One normalized upstream card; ``rank`` starts at 1 per source."""

    source: str
    category: str
    rank: int
    url: str
    title: str
    description: str = ''
    media_url: str | None = None


@dataclass(frozen=True)
class FusedResult:
    """One native result, with internal source evidence for diagnostics."""

    category: str
    url: str
    title: str
    description: str
    score: float
    source_ranks: tuple[tuple[str, int], ...]
    media_url: str | None = None


def canonical_result_url(url: object) -> str | None:
    """Build a conservative equality key for external HTTP(S) result URLs.

    The key removes fragments and known tracking parameters. Other query
    parameters retain their original order: changing them may change content.
    Never use this function as approval to *fetch* the URL from a server.
    """
    if not isinstance(url, str) or not 0 < len(url) <= 4096 or _CONTROL.search(url):
        return None
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None or '%' in parsed.netloc:
            return None
        host = parsed.hostname.encode('idna').decode('ascii').lower()
        if not host or host.startswith('.') or host.endswith('.') or '..' in host:
            return None
        port = parsed.port
        if port == 0:
            return None
        authority = host if ':' not in host else '[' + host + ']'
        if port and (parsed.scheme.lower(), port) not in (('https', 443), ('http', 80)):
            authority += ':' + str(port)
        params = parse_qsl(parsed.query, keep_blank_values=True)
        query = urlencode([
            (key, value) for key, value in params
            if not (key.lower().startswith('utm_') or key.lower() in _TRACKING_KEYS)
        ])
        path = parsed.path or '/'
        return urlunsplit((parsed.scheme.lower(), authority, path, query, ''))
    except (UnicodeError, ValueError):
        return None


def video_result_identity(url: object) -> str | None:
    """Normalize only *provably identical* YouTube video link representations.

    Different thumbnails, titles, channel pages and unrelated video-host URLs
    remain independent. This is an equality key, never a URL to visit, display,
    proxy, or send to a third party.
    """
    canonical = canonical_result_url(url)
    if canonical is None:
        return None
    parsed = urlsplit(canonical)
    # A nonstandard port can serve different content even at an official host.
    if parsed.port is not None:
        return canonical
    host = parsed.hostname
    video_id = None
    if host in _YOUTU_BE_HOSTS:
        parts = parsed.path.split('/')
        if len(parts) == 2:
            video_id = parts[1]
    elif host in _YOUTUBE_HOSTS:
        path_parts = parsed.path.split('/')
        if parsed.path == '/watch':
            values = [value for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                      if key == 'v']
            if len(values) == 1:
                video_id = values[0]
        elif (len(path_parts) == 3 and path_parts[1] in
              ('shorts', 'live', 'embed', 'v')):
            video_id = path_parts[2]
    if video_id is not None and _YOUTUBE_VIDEO_ID.fullmatch(video_id):
        return 'video:youtube:' + video_id
    return canonical


def _query_terms(query: str | None) -> tuple[str, ...]:
    """Bound query-text use to ranking in memory, never a fetch or log input.

    `None` opts out and exactly preserves pre-existing reciprocal-rank scores.
    A supplied query is validated before evaluating untrusted candidate cards.
    """
    if query is None:
        return ()
    if (not isinstance(query, str) or not 0 < len(query) <= 512
            or _QUERY_CONTROL.search(query)):
        raise ValueError('Invalid relevance query')
    terms = tuple(dict.fromkeys(term.casefold() for term in _LEXICAL_WORD.findall(query)))
    if not terms or len(terms) > _MAX_QUERY_TERMS or any(len(term) > 64 for term in terms):
        raise ValueError('Invalid bounded relevance terms')
    return terms


def _lexical_boost(title: str, description: str, terms: tuple[str, ...],
                   rrf_k: int) -> float:
    """Give modest, repeat-insensitive credit to explicit query-term overlap.

    Keep RRF primary: even a full title/description/phrase match can add at
    most 20 percent of a rank-one *single-source* vote. This is deterministic,
    term-based relevance, not semantic understanding or a spam-quality verdict.
    """
    if not terms:
        return 0.0
    title_words = tuple(term.casefold() for term in _LEXICAL_WORD.findall(title))
    description_words = {term.casefold() for term in _LEXICAL_WORD.findall(description)}
    target = set(terms)
    title_cover = len(target.intersection(title_words)) / len(target)
    description_cover = len(target & description_words) / len(target)
    phrase = (len(title_words) >= len(terms) and any(
        title_words[index:index + len(terms)] == terms
        for index in range(len(title_words) - len(terms) + 1)
    ))
    return ((0.14 * title_cover + 0.04 * description_cover
             + (0.02 if phrase else 0.0)) / (rrf_k + 1))


def fuse_results(
    candidates: Iterable[SourceResult], *, category: str, limit: int = 20,
    rrf_k: int = 60, query: str | None = None,
) -> list[FusedResult]:
    """Normalize and rank offline cards using RRF and optional bounded relevance.

    Every distinct source gives a URL at most one vote (at its best rank),
    preventing repeated cards from one provider from artificially boosting it.
    Invalid external result links are discarded without logging their contents.
    Images with no validated media URL remain separate because distinct images
    frequently originate from the same page; a page URL alone is not identity.

    This function makes no assertion that any named source is licensed or live.
    Upstream admission, request budgets and contractual permissions are separate
    gates that must run *before* provider dispatch and result use.
    The optional `query` signal never changes identity/dedup or source votes;
    absent a query, ordering and numeric scores remain exactly the old RRF.
    """
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError('Unsupported fusion category')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Invalid result limit')
    if type(rrf_k) is not int or not 1 <= rrf_k <= 1000:
        raise ValueError('Invalid fusion constant')
    terms = _query_terms(query)

    merged: dict[str, dict] = {}
    for ordinal, result in enumerate(candidates):
        if ordinal >= _MAX_CANDIDATES:
            raise ValueError('Result fusion input exceeds safe limit')
        if not isinstance(result, SourceResult) or result.category != category:
            raise ValueError('Result category mismatch')
        if not isinstance(result.source, str) or not _PROVIDER_ID.fullmatch(result.source):
            raise ValueError('Invalid source identity')
        if type(result.rank) is not int or not 1 <= result.rank <= 1000:
            raise ValueError('Invalid source rank')
        url_key = canonical_result_url(result.url)
        if (not url_key or not isinstance(result.title, str)
                or not result.title.strip() or len(result.title) > 512):
            continue
        if not isinstance(result.description, str) or len(result.description) > 2000:
            continue
        media_key = canonical_result_url(result.media_url) if result.media_url else None
        if result.media_url is not None and media_key is None:
            continue
        if category == 'images':
            identity = media_key
        elif category == 'videos':
            identity = video_result_identity(result.url)
        else:
            identity = url_key
        if identity is None:
            identity = 'unresolved-image:' + str(ordinal)

        group = merged.get(identity)
        if group is None:
            merged[identity] = {'card': result, 'first': ordinal, 'ranks': {result.source: result.rank}}
            continue
        old_rank = group['ranks'].get(result.source)
        if old_rank is None or result.rank < old_rank:
            group['ranks'][result.source] = result.rank
        # Prefer the highest-ranked source card for human-facing text, and
        # never allow a worse-ranked duplicate to replace its destination.
        if result.rank < group['card'].rank:
            group['card'] = result

    ordered = []
    for group in merged.values():
        card = group['card']
        ranks = tuple(sorted(group['ranks'].items()))
        score = (sum(1.0 / (rrf_k + rank) for _, rank in ranks)
                 + _lexical_boost(card.title, card.description, terms, rrf_k))
        ordered.append((score, group['first'], FusedResult(
            category=category, url=card.url, title=card.title,
            description=card.description, score=score, source_ranks=ranks,
            media_url=card.media_url,
        )))
    ordered.sort(key=lambda row: (-row[0], row[1]))
    return [result for _, _, result in ordered[:limit]]
