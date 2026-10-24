"""Offline tests for the owner-operated, read-only Search boundary probe."""

import io
import json
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch

from scripts import search_network_acceptance_probe as probe


PRIVATE = '100.71.27.119'
PUBLIC = '135.148.45.22'
PUBLIC_V6 = '2606:4700:4700::1111'  # Synthetic fixture only; no packet is sent.


class SearchBoundaryProbeTests(unittest.TestCase):
    def test_success_is_only_sampled_path_evidence(self):
        calls = []

        def local_fixture(host, address, path, timeout):
            calls.append((host, address, path, timeout))
            status = 200 if host == probe.PUBLIC_HOST or address == PRIVATE else 403
            return status, 'verified_tls'

        with patch.object(probe, '_probe_https', side_effect=local_fixture):
            result = probe.evaluate(PRIVATE, PUBLIC, PUBLIC_V6, timeout=3)
        self.assertEqual('pass_sampled_paths_only', result['status'])
        self.assertIs(result['production_release_authorized'], False)
        self.assertEqual(4, len(calls))
        self.assertEqual((probe.PRIVATE_HOST, PRIVATE, '/readyz', 3), calls[0])
        self.assertEqual((probe.PRIVATE_HOST, PUBLIC, '/readyz', 3), calls[1])
        self.assertEqual((probe.PUBLIC_HOST, PUBLIC, '/', 3), calls[2])
        self.assertEqual((probe.PRIVATE_HOST, PUBLIC_V6, '/readyz', 3), calls[3])

    def test_no_ipv6_cannot_silently_pass(self):
        with patch.object(probe, '_probe_https', return_value=(200, 'verified_tls')):
            result = probe.evaluate(PRIVATE, PUBLIC, None)
        self.assertEqual('blocked_do_not_release', result['status'])
        self.assertEqual('not_tested', result['probes']['private_direct_ipv6_denial']['status'])
        self.assertIs(result['ipv6_negative_tested'], False)

    def test_public_tls_failure_blocks_but_does_not_expose_error_message(self):
        def local_fixture(host, address, path, timeout):
            if host == probe.PUBLIC_HOST:
                return None, 'tls_failed'
            return (200 if address == PRIVATE else 403), 'verified_tls'

        with patch.object(probe, '_probe_https', side_effect=local_fixture):
            result = probe.evaluate(PRIVATE, PUBLIC, PUBLIC_V6)
        self.assertEqual('blocked_do_not_release', result['status'])
        self.assertEqual('tls_failed', result['probes']['public_https_ipv4']['tls'])
        serialized = json.dumps(result)
        self.assertNotIn(PRIVATE, serialized)
        self.assertNotIn(PUBLIC, serialized)
        self.assertNotIn(PUBLIC_V6, serialized)

    def test_fail_closed_on_private_denial_redirect_or_auth(self):
        for status in (200, 301, 302, 401, 404, 500):
            with self.subTest(status=status):
                def local_fixture(host, address, path, timeout):
                    if address == PRIVATE:
                        return 200, 'verified_tls'
                    if host == probe.PUBLIC_HOST:
                        return 200, 'verified_tls'
                    return status, 'verified_tls'

                with patch.object(probe, '_probe_https', side_effect=local_fixture):
                    result = probe.evaluate(PRIVATE, PUBLIC, PUBLIC_V6)
                self.assertEqual('blocked_do_not_release', result['status'])

    def test_fail_closed_on_tls_verification_failure_even_when_http_is_403(self):
        with patch.object(probe, '_probe_https', return_value=(403, 'tls_failed')):
            result = probe.evaluate(PRIVATE, PUBLIC, PUBLIC_V6)
        self.assertEqual('blocked_do_not_release', result['status'])
        self.assertEqual('blocked', result['probes']['private_direct_ipv4_denial']['status'])

    def test_network_role_validation_never_uses_dns(self):
        invalid = (
            (PRIVATE, '127.0.0.1', None),
            ('127.0.0.1', PUBLIC, None),
            ('search-dev.goreecloud.com', PUBLIC, None),
            (PRIVATE, '192.168.1.1', None),
            (PRIVATE, PUBLIC, 'fe80::1'),
            (PRIVATE, PUBLIC, '127.0.0.1'),
        )
        for private, public, ipv6 in invalid:
            with self.subTest(private=private, public=public, ipv6=ipv6):
                with patch.object(probe, '_probe_https') as never_called:
                    with self.assertRaises(ValueError):
                        probe.evaluate(private, public, ipv6)
                    never_called.assert_not_called()

    def test_invalid_timeout_is_blocked(self):
        for value in (0, 13, True, float('nan'), -1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    probe.evaluate(PRIVATE, PUBLIC, None, timeout=value)

    def test_cli_reports_only_bounded_status_without_addresses(self):
        with patch.object(probe, '_probe_https', return_value=(200, 'verified_tls')):
            captured = io.StringIO()
            with redirect_stdout(captured):
                exit_code = probe.main([
                    '--private-netbird-ip', PRIVATE, '--public-ipv4', PUBLIC,
                ])
        self.assertEqual(2, exit_code)
        body = json.loads(captured.getvalue())
        self.assertEqual('blocked_do_not_release', body['status'])
        self.assertNotIn(PRIVATE, captured.getvalue())
        self.assertNotIn(PUBLIC, captured.getvalue())

    def test_malformed_cli_input_cannot_perform_probe(self):
        with patch.object(probe, '_probe_https') as never_called:
            captured = io.StringIO()
            with redirect_stdout(captured):
                exit_code = probe.main(['--private-netbird-ip', 'localhost',
                                        '--public-ipv4', PUBLIC])
            self.assertEqual(2, exit_code)
            self.assertEqual('blocked_invalid_probe_configuration',
                             json.loads(captured.getvalue())['status'])
            never_called.assert_not_called()


if __name__ == '__main__':
    unittest.main()
