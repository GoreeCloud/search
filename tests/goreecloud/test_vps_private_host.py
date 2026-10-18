"""Private VPS reverse-proxy Host and Origin restrictions."""
import unittest
from searx.goreecloud_policy import validate_private_request_context, SearchPolicyViolation


class VPSPrivateHostTests(unittest.TestCase):
    def call_policy(self, **kwargs):
        defaults = dict(
            host='search-dev.goreecloud.com', scheme='http', method='POST',
            origin='https://search-dev.goreecloud.com', fetch_site='same-origin',
            allowed_public_host='search-dev.goreecloud.com',
        )
        defaults.update(kwargs)
        return validate_private_request_context(**defaults)

    def test_https_origin_behind_tls_proxy(self):
        self.call_policy()

    def test_host_is_never_permitted_by_default(self):
        with self.assertRaises(SearchPolicyViolation):
            self.call_policy(allowed_public_host=None)

    def test_reserved_stable_hostname_is_rejected(self):
        with self.assertRaises(SearchPolicyViolation):
            self.call_policy(host='search.goreecloud.com')

    def test_invalid_host_and_port_rejected(self):
        for host in ('evil.example', 'search-dev.goreecloud.com:8080',
                     'search-dev.goreecloud.com.evil.example', '127.0.0.2'):
            with self.subTest(host=host), self.assertRaises(SearchPolicyViolation):
                self.call_policy(host=host)

    def test_cross_origin_and_cross_site_rejected(self):
        for mutation in (
            {'origin': 'https://evil.example'},
            {'origin': 'http://search-dev.goreecloud.com'},
            {'fetch_site': 'cross-site'},
            {'allowed_public_host': 'evil.example'},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(SearchPolicyViolation):
                self.call_policy(**mutation)

    def test_local_host_still_supported(self):
        self.call_policy(host='127.0.0.1:8888', scheme='http',
                         origin='http://127.0.0.1:8888', allowed_public_host=None)
