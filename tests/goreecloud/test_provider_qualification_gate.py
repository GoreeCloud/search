"""Offline proof-of-coverage, never proof-of-release, for the 24-source matrix."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import provider_qualification_gate as gate


def report(category, *, state='results_observed', selected=None):
    providers = gate.CATEGORY_ENGINES[category]
    return {
        'development_only': True,
        'category': category,
        'results': [
            {
                'provider': provider,
                'state': state,
                'result_count': 1 if state in ('results_observed', 'partial_results') else 0,
                'error_count': 1 if state in ('partial_results', 'provider_error') else 0,
                'error_categories': ['access_denied']
                if state in ('partial_results', 'provider_error') else [],
            }
            for provider in (selected if selected is not None else providers)
        ],
    }


def all_reports():
    return [report(cat) for cat in gate.CATEGORY_ENGINES]


class ProviderQualificationGateTests(unittest.TestCase):
    def test_full_24_positive_matrix_is_coverage_only_not_release(self):
        outcome = gate.evaluate_reports(all_reports())
        self.assertEqual(24, outcome['expected_pairs'])
        self.assertEqual(24, outcome['reported_pairs'])
        self.assertEqual(24, outcome['results_observed_pairs'])
        self.assertTrue(outcome['provider_coverage_complete'])
        self.assertFalse(outcome['release_qualified'])
        self.assertTrue(outcome['independent_egress_and_licensing_evidence_required'])
        self.assertEqual(6, outcome['category_coverage']['images']['results_observed_pairs'])
        self.assertEqual(0, outcome['category_coverage']['images']['missing_pairs'])
        self.assertTrue(outcome['empty_does_not_confirm_provider_contact'])

    def test_missing_or_unresponsive_provider_fails_coverage(self):
        partial = gate.evaluate_reports(all_reports()[:-1])
        self.assertEqual(18, partial['reported_pairs'])
        self.assertEqual(6, len(partial['missing_pairs']))
        self.assertFalse(partial['provider_coverage_complete'])
        docs = all_reports()
        docs[0]['results'][0] = {
            'provider': 'brave', 'state': 'provider_error',
            'result_count': 0, 'error_count': 1, 'error_categories': ['rate_limited'],
        }
        outcome = gate.evaluate_reports(docs)
        self.assertEqual(23, outcome['results_observed_pairs'])
        self.assertFalse(outcome['provider_coverage_complete'])
        self.assertEqual([{'category': 'general', 'provider': 'brave'}],
                         outcome['unqualified_pairs'])
        self.assertEqual([{'category': 'general', 'provider': 'brave'}],
                         outcome['classified_provider_failures']['rate_limited'])
        self.assertEqual(1, outcome['category_coverage']['general']['provider_error_pairs'])

    def test_category_breakdown_exposes_missing_empty_partial_without_positive_claim(self):
        docs = all_reports()
        docs[1]['results'] = docs[1]['results'][1:]  # First Images source absent
        docs[1]['results'][0].update(state='no_results', result_count=0,
                                      error_count=0, error_categories=[])
        docs[1]['results'][1].update(state='partial_results', result_count=2,
                                      error_count=1, error_categories=['timeout', 'rate_limited'])
        summary = gate.evaluate_reports(docs)
        images = summary['category_coverage']['images']
        self.assertEqual(6, images['expected_pairs'])
        self.assertEqual(5, images['reported_pairs'])
        self.assertEqual(1, images['missing_pairs'])
        self.assertEqual(1, images['no_results_unconfirmed_pairs'])
        self.assertEqual(1, images['partial_results_pairs'])
        self.assertEqual(3, images['results_observed_pairs'])
        self.assertFalse(summary['provider_coverage_complete'])
        self.assertEqual([{'category': 'images', 'provider': 'qwant'}],
                         summary['classified_provider_failures']['timeout'])

    def test_malformed_or_fabricated_coverage_fails_closed(self):
        cases = []
        docs = all_reports()
        docs[0]['results'][0]['state'] = 'results_observed'
        docs[0]['results'][0]['result_count'] = 0
        cases.append(docs)
        docs = all_reports()
        docs[0]['results'][0]['error_count'] = 1
        cases.append(docs)
        docs = all_reports()
        docs[0]['results'][0]['result_count'] = True
        cases.append(docs)
        docs = all_reports()
        docs[0]['results'][0]['error_categories'] = ['private query=https://example.com']
        cases.append(docs)
        docs = all_reports()
        docs[0]['results'][0]['url'] = 'https://private.example.org/secret'
        cases.append(docs)
        docs = all_reports()
        docs[0]['results'][0]['provider'] = 'unapproved_provider'
        cases.append(docs)
        docs = all_reports()
        docs[0]['results'].append(docs[0]['results'][0])
        cases.append(docs)
        docs = all_reports()
        docs[0]['development_only'] = False
        cases.append(docs)
        docs = all_reports()
        docs[0]['raw_search_terms'] = 'sensitive'
        cases.append(docs)
        docs = all_reports()
        docs[0]['results'][0].pop('error_categories')
        cases.append(docs)
        docs = all_reports()
        docs[0]['results'][0]['state'] = 'unknown'
        cases.append(docs)
        docs = all_reports()
        docs[0]['results'][0]['provider'] = ['brave']
        cases.append(docs)
        docs = all_reports()
        docs[0]['category'] = ['general']
        cases.append(docs)
        for index, item in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(gate.InvalidEvidence):
                gate.evaluate_reports(item)

    def test_invalid_state_count_pairs_fail_closed(self):
        for state, n, e, kinds in (
            ('partial_results', 0, 1, ['timeout']),
            ('provider_error', 1, 1, ['timeout']),
            ('no_results', 0, 1, ['timeout']),
            ('results_observed', 1, 0, ['other_error']),
        ):
            docs = all_reports()
            docs[0]['results'][0].update(
                state=state, result_count=n, error_count=e, error_categories=kinds)
            with self.subTest(state=state), self.assertRaises(gate.InvalidEvidence):
                gate.evaluate_reports(docs)

    def test_no_report_cli_never_contacts_provider(self):
        with patch('builtins.print') as printer:
            self.assertEqual(64, gate.main([]))
        printer.assert_called_once()

    def test_cli_reports_only_bounded_source_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for doc in all_reports():
                path = Path(directory) / (doc['category'] + '.json')
                path.write_text(json.dumps(doc), encoding='utf-8')
                paths.append(str(path))
            sink = StringIO()
            with contextlib.redirect_stdout(sink):
                self.assertEqual(0, gate.main(paths))
            output = json.loads(sink.getvalue())
            self.assertTrue(output['provider_coverage_complete'])
            self.assertFalse(output['release_qualified'])
            self.assertNotIn(directory, sink.getvalue())
            # Alter one file: reject unapproved fields without echoing text.
            doc = all_reports()[0]
            doc['sensitive'] = 'confidential query'
            Path(paths[0]).write_text(json.dumps(doc), encoding='utf-8')
            sink = StringIO()
            with contextlib.redirect_stdout(sink):
                self.assertEqual(2, gate.main(paths))
            self.assertNotIn('confidential', sink.getvalue())
            self.assertNotIn(directory, sink.getvalue())

    def test_duplicate_pair_across_reports_is_rejected(self):
        docs = all_reports()
        docs.append(report('general', selected=['brave']))
        with self.assertRaises(gate.InvalidEvidence):
            gate.evaluate_reports(docs)

    def test_cli_rejects_ambiguous_json_and_never_echoes_raw_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ambiguous.json'
            for payload, reason in (
                ('{"development_only":true,"development_only":false,"category":"images","results":[]}',
                 'duplicate_json_field'),
                ('{"development_only":true,"category":"images","results":[],"secret":NaN}',
                 'nonfinite_json_value'),
            ):
                path.write_text(payload, encoding='utf-8')
                sink = StringIO()
                with contextlib.redirect_stdout(sink):
                    self.assertEqual(2, gate.main([str(path)]))
                output = json.loads(sink.getvalue())
                self.assertEqual(reason, output['reason'])
                self.assertNotIn(directory, sink.getvalue())
                self.assertNotIn('secret', sink.getvalue())


if __name__ == '__main__':
    unittest.main()
