#!/usr/bin/env python3
"""Offline, bounded coverage check for sanitized provider-health reports.

This never performs network I/O. A PASS means reports are structurally
consistent, not that their provenance is authenticated, provider access is
lawful, privacy is verified, or GoreeCloud Search is ready for release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from scripts.provider_health_probe import CATEGORY_ENGINES

EXPECTED = frozenset(
    (category, provider)
    for category, providers in CATEGORY_ENGINES.items()
    for provider in providers
)
STATES = frozenset({
    'results_observed', 'partial_results', 'provider_error', 'no_results',
    'invalid_response_contract', 'selection_mismatch', 'invalid_error_contract',
    'invalid_result_contract', 'invalid_result_attribution',
    'invalid_representation_contract', 'request_or_decode_error', 'response_too_large',
})
ERROR_CATEGORIES = frozenset({
    'timeout', 'rate_limited', 'challenge', 'access_denied',
    'upstream_http_error', 'upstream_api_error', 'engine_error',
    'parsing_error', 'network_error', 'other_error',
})
REPORT_KEYS = frozenset({'development_only', 'category', 'results'})
OUTCOME_KEYS = frozenset({
    'provider', 'state', 'result_count', 'error_count',
    'error_categories', 'error_type',
})
MAX_REPORT_BYTES = 65536


class InvalidEvidence(ValueError):
    """An evidence document is malformed, ambiguous or discloses extra data."""


def _unique_fields(pairs: list[tuple[str, object]]) -> dict:
    """Reject JSON ambiguity before source/status evidence is considered."""
    fields = {}
    for name, value in pairs:
        if name in fields:
            raise InvalidEvidence('duplicate_json_field')
        fields[name] = value
    return fields


def _reject_constant(_value: str) -> None:
    raise InvalidEvidence('nonfinite_json_value')


def _nonnegative_int(value: object) -> bool:
    return type(value) is int and 0 <= value <= 1000000


def evaluate_reports(documents: list[object]) -> dict:
    """Check the complete approved matrix, without accepting extra content."""
    if not documents:
        raise InvalidEvidence('no_reports')
    observed = {}
    observed_error_categories = {}
    for doc in documents:
        if not isinstance(doc, dict) or set(doc) != REPORT_KEYS:
            raise InvalidEvidence('report_contract')
        category = doc['category']
        if (doc['development_only'] is not True or not isinstance(category, str)
                or category not in CATEGORY_ENGINES):
            raise InvalidEvidence('report_scope')
        outcomes = doc['results']
        if not isinstance(outcomes, list) or len(outcomes) > len(CATEGORY_ENGINES[category]):
            raise InvalidEvidence('report_results')
        for item in outcomes:
            if not isinstance(item, dict) or not {'provider', 'state'}.issubset(item):
                raise InvalidEvidence('outcome_contract')
            if not set(item).issubset(OUTCOME_KEYS):
                raise InvalidEvidence('unapproved_outcome_fields')
            provider, state = item['provider'], item['state']
            if not isinstance(provider, str) or not isinstance(state, str):
                raise InvalidEvidence('invalid_outcome_types')
            pair = (category, provider)
            if pair not in EXPECTED or state not in STATES:
                raise InvalidEvidence('unapproved_category_or_state')
            if pair in observed:
                raise InvalidEvidence('duplicate_provider_category')
            has_counts = {'result_count', 'error_count', 'error_categories'}.issubset(item)
            if has_counts:
                if (not _nonnegative_int(item['result_count'])
                        or not _nonnegative_int(item['error_count'])
                        or not isinstance(item['error_categories'], list)
                        or len(item['error_categories']) > len(ERROR_CATEGORIES)
                        or any(not isinstance(x, str) or x not in ERROR_CATEGORIES
                               for x in item['error_categories'])
                        or len(set(item['error_categories'])) != len(item['error_categories'])):
                    raise InvalidEvidence('invalid_counts_or_error_category')
            elif any(key in item for key in ('result_count', 'error_count', 'error_categories')):
                raise InvalidEvidence('incomplete_counts')
            if state in ('results_observed', 'partial_results', 'provider_error', 'no_results'):
                if not has_counts:
                    raise InvalidEvidence('missing_counts')
                n, e, kinds = (item['result_count'],
                                item['error_count'], item['error_categories'])
                if state == 'results_observed' and not (n > 0 and e == 0 and not kinds):
                    raise InvalidEvidence('false_success')
                if state == 'partial_results' and not (n > 0 and e > 0 and kinds):
                    raise InvalidEvidence('false_partial_results')
                if state == 'provider_error' and not (n == 0 and e > 0 and kinds):
                    raise InvalidEvidence('false_provider_error')
                if state == 'no_results' and not (n == 0 and e == 0 and not kinds):
                    raise InvalidEvidence('false_no_results')
            elif has_counts:
                raise InvalidEvidence('unexpected_error_counts')
            if 'error_type' in item and (state != 'request_or_decode_error'
                                        or item['error_type'] not in (
                                            'OSError', 'ValueError', 'TypeError',
                                            'JSONDecodeError', 'HTTPError', 'URLError')):
                raise InvalidEvidence('invalid_error_type')
            observed[pair] = state
            observed_error_categories[pair] = tuple(item['error_categories']) if has_counts else ()

    missing = sorted(EXPECTED.difference(observed))
    failures = sorted(pair for pair, state in observed.items()
                      if state != 'results_observed')
    covered = len(observed)
    # Do not conflate configured/selected sources, represented result links,
    # provider contact, and an actually useful set of search results.
    # Every number here is derived only from explicitly supplied sanitized
    # diagnostic states, with no query text, links, titles or error messages.
    by_category = {}
    for category, providers in CATEGORY_ENGINES.items():
        expected_pairs = {(category, provider) for provider in providers}
        seen = {pair: state for pair, state in observed.items() if pair in expected_pairs}
        by_category[category] = {
            'expected_pairs': len(expected_pairs),
            'reported_pairs': len(seen),
            'missing_pairs': len(expected_pairs) - len(seen),
            'results_observed_pairs': sum(state == 'results_observed' for state in seen.values()),
            'partial_results_pairs': sum(state == 'partial_results' for state in seen.values()),
            'no_results_unconfirmed_pairs': sum(state == 'no_results' for state in seen.values()),
            'provider_error_pairs': sum(state == 'provider_error' for state in seen.values()),
            'invalid_or_transport_error_pairs': sum(
                state not in ('results_observed', 'partial_results', 'no_results', 'provider_error')
                for state in seen.values()
            ),
        }
    failure_reasons = {
        reason: [
            {'category': category, 'provider': provider}
            for (category, provider), kinds in sorted(observed_error_categories.items())
            if reason in kinds
        ]
        for reason in sorted(ERROR_CATEGORIES)
        if any(reason in kinds for kinds in observed_error_categories.values())
    }
    return {
        'scope': 'development_probe_report_coverage_only',
        'expected_pairs': len(EXPECTED),
        'reported_pairs': covered,
        'results_observed_pairs': sum(s == 'results_observed' for s in observed.values()),
        'missing_pairs': [{'category': c, 'provider': p} for c, p in missing],
        'unqualified_pairs': [{'category': c, 'provider': p} for c, p in failures],
        'category_coverage': by_category,
        'classified_provider_failures': failure_reasons,
        'empty_does_not_confirm_provider_contact': True,
        'provider_coverage_complete': not missing and not failures,
        'release_qualified': False,
        'independent_egress_and_licensing_evidence_required': True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', nargs='*', type=Path, help='sanitized probe JSON report files')
    args = parser.parse_args(argv)
    if not args.reports:
        print('No files read or provider requests sent. Supply sanitized probe JSON reports.')
        return 64
    try:
        if len(args.reports) > 24:
            raise InvalidEvidence('too_many_reports')
        documents = []
        for path in args.reports:
            with path.open('rb') as stream:
                data = stream.read(MAX_REPORT_BYTES + 1)
            if len(data) > MAX_REPORT_BYTES:
                raise InvalidEvidence('oversized_report')
            documents.append(json.loads(data.decode('utf-8'),
                                        object_pairs_hook=_unique_fields,
                                        parse_constant=_reject_constant))
        summary = evaluate_reports(documents)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        # No file paths, provider text, URL or contents are ever echoed.
        reason = str(exc) if isinstance(exc, InvalidEvidence) else 'invalid_document'
        print(json.dumps({'state': 'invalid_evidence', 'reason': reason,
                          'release_qualified': False}, sort_keys=True))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary['provider_coverage_complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
