"""Development hostname must never be promoted by copying a public vhost."""

import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SEARXNG_SETTINGS_PATH', str(ROOT / 'configs/goreecloud/settings.free-first.yml'))
os.environ.setdefault('SEARXNG_SECRET', 'goreecloud-host-boundary-tests-only-000000')

from searx.goreecloud_policy import SearchPolicyViolation, validate_private_request_context


class SearchHostnameBoundaryTests(unittest.TestCase):
    def test_private_caddy_template_has_vpn_acl_and_explicit_deny(self):
        config = (ROOT / 'deploy/vps/Caddyfile.search').read_text(encoding='utf-8')
        self.assertIn('search-dev.goreecloud.com {', config)
        self.assertIn('@netbird_client remote_ip 100.64.0.0/10', config)
        self.assertIn('handle @netbird_client {', config)
        self.assertIn('respond "Forbidden" 403', config)
        # Owner's future public service is a distinct release boundary.
        self.assertNotIn('\nsearch.goreecloud.com {', config)

    def test_private_app_rejects_public_hostname_even_with_valid_origin(self):
        with self.assertRaises(SearchPolicyViolation):
            validate_private_request_context(
                host='search.goreecloud.com', scheme='https', method='POST',
                origin='https://search.goreecloud.com', fetch_site='same-origin',
                allowed_public_host='search-dev.goreecloud.com',
            )

    def test_private_app_permits_only_exact_development_host(self):
        validate_private_request_context(
            host='search-dev.goreecloud.com', scheme='https', method='POST',
            origin='https://search-dev.goreecloud.com', fetch_site='same-origin',
            allowed_public_host='search-dev.goreecloud.com',
        )
        for host in ('search-dev.goreecloud.com.evil.invalid',
                     'other-dev.goreecloud.com', 'search-dev.goreecloud.com:443'):
            with self.subTest(host=host), self.assertRaises(SearchPolicyViolation):
                validate_private_request_context(
                    host=host, scheme='https', method='GET', origin=None,
                    fetch_site=None, allowed_public_host='search-dev.goreecloud.com',
                )


if __name__ == '__main__':
    unittest.main()
