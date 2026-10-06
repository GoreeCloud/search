from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit

from .models import ParsedQuery
from .normalization import NormalizedResult


@dataclass(frozen=True, slots=True)
class RankingSignal:
    code: str
    score: float
    explanation: str


@dataclass(frozen=True, slots=True)
class RankedResult:
    result: NormalizedResult
    score: float
    signals: tuple[RankingSignal, ...]

    @property
    def explanations(self) -> tuple[str, ...]:
        return tuple(signal.explanation for signal in self.signals)


def _contains(text: str, value: str) -> bool:
    return value.casefold() in text.casefold()


def _host_matches(host: str, domain: str) -> bool:
    host = host.casefold().rstrip(".")
    domain = domain.casefold().rstrip(".")
    return host == domain or host.endswith(f".{domain}")


def _matches_result_filters(
    query: ParsedQuery,
    result: NormalizedResult,
    excluded_patterns: tuple[re.Pattern[str], ...],
) -> bool:
    """Apply explicit result restrictions after normalization, never as an auth gate.

    Exclusions inspect the title/snippet we can actually show; providers are
    still responsible for honoring filters against content not returned here.
    """
    parts = urlsplit(result.canonical_url)
    host = parts.hostname or ""
    if query.filters.sites and not any(_host_matches(host, site) for site in query.filters.sites):
        return False
    if any(_host_matches(host, domain) for domain in query.filters.excluded_domains):
        return False
    if query.filters.filetypes and not any(
        parts.path.casefold().endswith(f".{ext.casefold()}") for ext in query.filters.filetypes
    ):
        return False
    if excluded_patterns:
        visible_text = f"{result.title}\n{result.snippet}".casefold()
        if any(pattern.search(visible_text) for pattern in excluded_patterns):
            return False
    return True


def _score_result(query: ParsedQuery, result: NormalizedResult) -> tuple[float, tuple[RankingSignal, ...]]:
    signals: list[RankingSignal] = []
    title = result.title.casefold()
    snippet = result.snippet.casefold()

    phrase_title_matches = [phrase for phrase in query.phrases if phrase.casefold() in title]
    phrase_snippet_matches = [
        phrase for phrase in query.phrases
        if phrase.casefold() in snippet and phrase not in phrase_title_matches
    ]
    if phrase_title_matches:
        score = 20.0 * len(phrase_title_matches)
        signals.append(
            RankingSignal(
                "phrase_title_match",
                score,
                f"Quoted phrase matched the title ({len(phrase_title_matches)} match{'es' if len(phrase_title_matches) != 1 else ''}).",
            )
        )
    if phrase_snippet_matches:
        score = 8.0 * len(phrase_snippet_matches)
        signals.append(
            RankingSignal(
                "phrase_snippet_match",
                score,
                f"Quoted phrase matched the snippet ({len(phrase_snippet_matches)} match{'es' if len(phrase_snippet_matches) != 1 else ''}).",
            )
        )

    title_terms = [term for term in query.terms if _contains(title, term)]
    snippet_terms = [term for term in query.terms if term not in title_terms and _contains(snippet, term)]
    if title_terms:
        score = 4.0 * len(title_terms)
        signals.append(
            RankingSignal(
                "title_term_match",
                score,
                f"Query terms matched the title ({len(title_terms)} of {len(query.terms)}).",
            )
        )
    if snippet_terms:
        score = 1.5 * len(snippet_terms)
        signals.append(
            RankingSignal(
                "snippet_term_match",
                score,
                f"Additional query terms matched the snippet ({len(snippet_terms)}).",
            )
        )
    if query.terms and len(title_terms) == len(query.terms):
        signals.append(
            RankingSignal(
                "all_terms_in_title",
                8.0,
                "All free-text query terms are present in the title.",
            )
        )

    host = urlsplit(result.canonical_url).hostname or ""
    if query.filters.sites and any(_host_matches(host, site) for site in query.filters.sites):
        signals.append(
            RankingSignal(
                "site_restriction_match",
                6.0,
                "Result matches the explicit site restriction.",
            )
        )

    if query.filters.filetypes:
        path = urlsplit(result.canonical_url).path.casefold()
        if any(path.endswith(f".{ext.casefold()}") for ext in query.filters.filetypes):
            signals.append(
                RankingSignal(
                    "filetype_match",
                    4.0,
                    "Result URL matches the requested file type.",
                )
            )

    if query.filters.language and result.language:
        if result.language.casefold() == query.filters.language.casefold():
            signals.append(
                RankingSignal(
                    "language_match",
                    3.0,
                    "Result language matches the explicit language preference.",
                )
            )

    agreement_bonus = min(max(result.source_agreement - 1, 0), 4) * 1.5
    if agreement_bonus:
        signals.append(
            RankingSignal(
                "source_agreement",
                agreement_bonus,
                f"The same result was found by {result.source_agreement} declared sources.",
            )
        )

    if any(item.indexed_by_goreecloud for item in result.provenance):
        signals.append(
            RankingSignal(
                "indexed_by_goreecloud",
                0.0,
                "The result is present in GoreeCloud Index.",
            )
        )

    total = round(sum(signal.score for signal in signals), 3)
    return total, tuple(signals)


def rank_results(query: ParsedQuery, results: tuple[NormalizedResult, ...] | list[NormalizedResult]) -> tuple[RankedResult, ...]:
    """Apply explicit result restrictions, then deterministically rank matches.

    This output filtering is not a substitute for provider-side query filtering
    or an authorization/privacy boundary.
    """
    excluded_patterns = tuple(
        re.compile(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)")
        for term in query.excluded_terms
    )
    ranked = [
        RankedResult(result=result, score=score, signals=signals)
        for result in results
        if _matches_result_filters(query, result, excluded_patterns)
        for score, signals in [_score_result(query, result)]
    ]
    ranked.sort(
        key=lambda item: (
            -item.score,
            -item.result.source_agreement,
            item.result.canonical_url.casefold(),
            item.result.result_id,
        )
    )
    return tuple(ranked)
