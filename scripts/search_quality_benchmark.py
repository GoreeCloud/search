#!/usr/bin/env python3
"""Offline, aggregate-only quality gate for GoreeCloud-owned result fusion.

This intentionally neither imports provider transports nor makes network calls.
Only synthetic/nonpersonal fixture data belongs here. A passing fixture proves
the deterministic fusion contract for that fixture, never live search quality,
provider coverage, legal rights, or release readiness.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

# Also work when launched as ``python3 scripts/search_quality_benchmark.py``
# from the repository root, without relying on an installed Search package.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from native_search.fusion import (
    SourceResult, SUPPORTED_CATEGORIES, canonical_result_url, fuse_results,
    video_result_identity,
)


MAX_FIXTURE_BYTES = 131072
MAX_CANDIDATES = 100
MAX_SOURCES = 12
MAX_RELEVANT = 100
SOURCE_ID = re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')
STATES = frozenset({'ok', 'empty', 'timeout', 'rate_limited', 'access_denied', 'error'})
REQUIRED_GATES = frozenset({
    'min_distinct', 'min_contributing_sources', 'min_relevant_at_10',
    'min_recall_percent_at_10', 'max_missing_image_media',
    'require_all_sources_healthy',
})
OPTIONAL_GATES = frozenset({
    'min_sources_with_unique_at_10', 'min_reciprocal_rank_percent_at_10',
})


class InvalidBenchmark(ValueError):
    """Invalid or unsafe fixture; message is a fixed, non-sensitive code."""


def _integer(value: object, *, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _identity(value: object, *, category: str = 'web') -> str:
    identity = (video_result_identity(value) if category == 'videos'
                else canonical_result_url(value))
    if identity is None:
        raise InvalidBenchmark('invalid_result_url')
    return identity


def _parse_fixture(fixture: object) -> tuple[str, list[dict], list[SourceResult], set[str], dict, int]:
    if not isinstance(fixture, dict) or set(fixture) != {
            'development_only', 'category', 'sources', 'relevant', 'gates'}:
        raise InvalidBenchmark('fixture_contract')
    category = fixture['category']
    if (fixture['development_only'] is not True or not isinstance(category, str)
            or category not in SUPPORTED_CATEGORIES):
        raise InvalidBenchmark('development_category_required')
    providers = fixture['sources']
    if not isinstance(providers, list) or not 1 <= len(providers) <= MAX_SOURCES:
        raise InvalidBenchmark('source_budget')
    gates = fixture['gates']
    if (not isinstance(gates, dict) or not REQUIRED_GATES.issubset(gates)
            or not set(gates).issubset(REQUIRED_GATES | OPTIONAL_GATES)):
        raise InvalidBenchmark('gates_contract')
    for key, upper in (
        ('min_distinct', MAX_CANDIDATES), ('min_contributing_sources', MAX_SOURCES),
        ('min_relevant_at_10', 10), ('min_recall_percent_at_10', 100),
        ('max_missing_image_media', MAX_CANDIDATES),
    ):
        lower = 0 if key == 'max_missing_image_media' else 1
        if not _integer(gates[key], minimum=lower, maximum=upper):
            raise InvalidBenchmark('gate_range')
    if type(gates['require_all_sources_healthy']) is not bool:
        raise InvalidBenchmark('gate_type')
    if ('min_sources_with_unique_at_10' in gates and
            not _integer(gates['min_sources_with_unique_at_10'], minimum=0,
                         maximum=MAX_SOURCES)):
        raise InvalidBenchmark('gate_range')
    if ('min_reciprocal_rank_percent_at_10' in gates and
            not _integer(gates['min_reciprocal_rank_percent_at_10'], minimum=1,
                         maximum=100)):
        raise InvalidBenchmark('gate_range')
    if (gates['min_contributing_sources'] > len(providers) or
            gates.get('min_sources_with_unique_at_10', 0) > len(providers)):
        raise InvalidBenchmark('unachievable_source_gate')

    relevant = fixture['relevant']
    if not isinstance(relevant, list) or not 1 <= len(relevant) <= MAX_RELEVANT:
        raise InvalidBenchmark('relevance_judgments_required')
    identities = [_identity(item, category=category) for item in relevant]
    if len(identities) != len(set(identities)):
        raise InvalidBenchmark('duplicate_relevance_judgment')
    if gates['min_relevant_at_10'] > len(identities):
        raise InvalidBenchmark('unachievable_relevance_gate')

    cards: list[SourceResult] = []
    seen = set()
    missing_media = 0
    for provider in providers:
        if not isinstance(provider, dict) or set(provider) != {'source', 'state', 'results'}:
            raise InvalidBenchmark('source_contract')
        source, state, rows = (provider['source'], provider['state'], provider['results'])
        if not isinstance(source, str) or SOURCE_ID.fullmatch(source) is None or source in seen:
            raise InvalidBenchmark('source_identity')
        seen.add(source)
        if (not isinstance(state, str) or state not in STATES
                or not isinstance(rows, list) or len(rows) > MAX_CANDIDATES):
            raise InvalidBenchmark('source_state')
        if (state == 'ok' and not rows) or (state != 'ok' and rows):
            raise InvalidBenchmark('source_result_mismatch')
        for row in rows:
            if not isinstance(row, dict) or not {'rank', 'url', 'title'}.issubset(row):
                raise InvalidBenchmark('result_contract')
            if not set(row).issubset({'rank', 'url', 'title', 'description', 'media_url'}):
                raise InvalidBenchmark('result_fields')
            rank = row['rank']
            if not _integer(rank, minimum=1, maximum=1000):
                raise InvalidBenchmark('result_rank')
            _identity(row['url'])
            title, description, media = (row['title'], row.get('description', ''),
                                         row.get('media_url'))
            if not isinstance(title, str) or not 0 < len(title.strip()) <= 512:
                raise InvalidBenchmark('result_title')
            if not isinstance(description, str) or len(description) > 2000:
                raise InvalidBenchmark('result_description')
            if media is not None:
                _identity(media)
            elif category == 'images':
                missing_media += 1
            cards.append(SourceResult(source=source, category=category, rank=rank,
                                      url=row['url'], title=title,
                                      description=description, media_url=media))
            if len(cards) > MAX_CANDIDATES:
                raise InvalidBenchmark('candidate_budget')
    return category, providers, cards, set(identities), gates, missing_media


def evaluate_fixture(fixture: object) -> dict:
    """Return sanitized aggregate metrics and exact gate failures only."""
    category, providers, cards, relevant, gates, missing_media = _parse_fixture(fixture)
    fused = fuse_results(cards, category=category, limit=100)
    top = fused[:10]
    def result_identity(item: object) -> str:
        if category == 'images':
            return canonical_result_url(item.media_url) or ''
        return _identity(item.url, category=category)

    found = sum(result_identity(item) in relevant for item in top)
    first = next((index for index, item in enumerate(top, 1)
                  if result_identity(item) in relevant), None)
    contributing = set(source for item in fused for source, _ in item.source_ranks)
    top_unique = [item for item in top if len(item.source_ranks) == 1]
    unique_sources = {item.source_ranks[0][0] for item in top_unique}
    failed = sorted(p['source'] for p in providers if p['state'] not in ('ok', 'empty'))
    empty = sorted(p['source'] for p in providers if p['state'] == 'empty')
    reasons = []
    if len(fused) < gates['min_distinct']:
        reasons.append('insufficient_distinct_results')
    if len(contributing) < gates['min_contributing_sources']:
        reasons.append('insufficient_contributing_sources')
    if len(unique_sources) < gates.get('min_sources_with_unique_at_10', 0):
        reasons.append('insufficient_unique_source_discovery_at_10')
    if found < gates['min_relevant_at_10']:
        reasons.append('insufficient_relevant_at_10')
    reciprocal_rank_percent = 100 // first if first else 0
    if reciprocal_rank_percent < gates.get('min_reciprocal_rank_percent_at_10', 0):
        reasons.append('insufficient_first_relevant_rank_at_10')
    recall_percent = (100 * found) // len(relevant)
    if recall_percent < gates['min_recall_percent_at_10']:
        reasons.append('insufficient_recall_at_10')
    if missing_media > gates['max_missing_image_media']:
        reasons.append('missing_image_media_identity')
    if gates['require_all_sources_healthy'] and failed:
        reasons.append('source_degraded')

    return {
        'scope': 'synthetic_fusion_quality_only', 'development_only': True,
        'release_qualified': False, 'category': category,
        'candidate_count': len(cards), 'distinct_results': len(fused),
        'collapsed_duplicates': len(cards) - len(fused),
        'configured_sources': len(providers),
        'contributing_sources': len(contributing),
        'unique_results_at_10': len(top_unique),
        'sources_with_unique_at_10': len(unique_sources),
        'failed_sources': failed, 'empty_sources': empty,
        'missing_image_media_identity': missing_media,
        'judged_relevant': len(relevant), 'relevant_at_10': found,
        'recall_percent_at_10': recall_percent,
        'precision_percent_at_10': 10 * found,
        'reciprocal_rank_at_10': round(1.0 / first, 4) if first else 0.0,
        'reciprocal_rank_percent_at_10': reciprocal_rank_percent,
        'passed': not reasons, 'failed_gates': reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixtures', nargs='*', type=Path,
                        help='bounded, fully synthetic benchmark JSON files')
    args = parser.parse_args(argv)
    if not args.fixtures:
        print('No provider requests sent. Supply synthetic quality fixtures.')
        return 64
    try:
        if len(args.fixtures) > 10:
            raise InvalidBenchmark('fixture_budget')
        outcomes = []
        for path in args.fixtures:
            with path.open('rb') as stream:
                payload = stream.read(MAX_FIXTURE_BYTES + 1)
            if len(payload) > MAX_FIXTURE_BYTES:
                raise InvalidBenchmark('fixture_oversized')
            outcomes.append(evaluate_fixture(json.loads(payload.decode('utf-8'))))
    except InvalidBenchmark as exc:
        print(json.dumps({'state': 'invalid_fixture', 'reason': str(exc),
                          'release_qualified': False}, sort_keys=True))
        return 2
    except (OSError, UnicodeError, ValueError, TypeError):
        print(json.dumps({'state': 'invalid_fixture', 'reason': 'invalid_document',
                          'release_qualified': False}, sort_keys=True))
        return 2
    passed = all(outcome['passed'] for outcome in outcomes)
    print(json.dumps({'state': 'pass' if passed else 'fail', 'development_only': True,
                      'release_qualified': False, 'cases': outcomes}, sort_keys=True))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
