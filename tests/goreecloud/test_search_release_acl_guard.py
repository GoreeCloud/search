"""Adversarial offline checks for Search Development's actual Caddy ACL shape."""

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from scripts import search_development_ingress_guard as guard
from scripts.search_development_ingress_guard import private_search_ingress_is_safe
from test_free_upgrade_preflight import m, evaluate, SITE


ROOT = Path(__file__).resolve().parents[2]
OLD = m.LEGACY_ROUTE.old
PUBLIC = "search.goreecloud.com"


class SearchReleaseAclGuardTests(unittest.TestCase):
    def test_existing_dev_caddy_template_passes_with_its_exact_gateway(self):
        content = (ROOT / "deploy/vps/Caddyfile.search").read_text(encoding="utf-8")
        self.assertTrue(private_search_ingress_is_safe(content, "goreecloud-search-gateway:8080"))
        self.assertFalse(private_search_ingress_is_safe(content, OLD))

    def test_existing_release_fixture_passes_as_manual_review_only(self):
        self.assertTrue(private_search_ingress_is_safe(SITE.decode(), OLD))
        self.assertEqual("admitted_for_manual_cutover_review", evaluate()["status"])

    def test_private_site_can_coexist_with_unrelated_caddy_hosts(self):
        config = SITE.decode() + '\nother.example {\n    respond "ok"\n}\n'
        self.assertTrue(private_search_ingress_is_safe(config, OLD))

    def test_future_public_site_must_not_proxy_private_development(self):
        good = SITE.decode() + '\n' + PUBLIC + ' {\n    respond "not yet released" 503\n}\n'
        self.assertTrue(private_search_ingress_is_safe(good, OLD))
        bad = SITE.decode() + '\n' + PUBLIC + ' {\n    reverse_proxy ' + OLD + '\n}\n'
        self.assertFalse(private_search_ingress_is_safe(bad, OLD))

    def test_extra_dev_hostname_alias_fails(self):
        bad = SITE.decode() + '\nsearch-dev.goreecloud.com, search.goreecloud.com {\n    respond "ok"\n}\n'
        self.assertFalse(private_search_ingress_is_safe(bad, OLD))

    def test_matcher_and_deny_in_comments_do_not_count(self):
        bad = SITE.decode().replace(
            "@netbird_client remote_ip 100.64.0.0/10",
            "# @netbird_client remote_ip 100.64.0.0/10",
        )
        self.assertFalse(private_search_ingress_is_safe(bad, OLD))
        bad = SITE.decode().replace('respond "Forbidden" 403', '# respond "Forbidden" 403')
        self.assertFalse(private_search_ingress_is_safe(bad, OLD))

    def test_fail_closed_when_catchall_proxy_precedes_acl(self):
        bad = SITE.decode().replace(
            "    @netbird_client remote_ip",
            "    reverse_proxy " + OLD + "\n    @netbird_client remote_ip",
        )
        self.assertFalse(private_search_ingress_is_safe(bad, OLD))
        self.assertEqual("blocked_do_not_cutover", evaluate(source=bad.encode(), snapshot=bad.encode())["status"])
        check = next(c for c in evaluate(source=bad.encode(), snapshot=bad.encode())["checks"]
                     if c["check"] == "unique_netbird_only_host")
        self.assertFalse(check["passed"])

    def test_fail_closed_when_other_matcher_handles_public_clients(self):
        bad = SITE.decode().replace(
            '    handle {\n        respond "Forbidden" 403\n    }',
            '    handle {\n        reverse_proxy ' + OLD + '\n    }',
        )
        self.assertFalse(private_search_ingress_is_safe(bad, OLD))

    def test_fail_closed_on_acl_rewrites_widening_or_obscuring_policy(self):
        replacements = (
            ("100.64.0.0/10", "0.0.0.0/0"),
            ("handle @netbird_client", "handle"),
            ('respond "Forbidden" 403', 'respond "ok" 200'),
            ('respond "Forbidden" 403', 'redir https://search.goreecloud.com'),
            ("reverse_proxy " + OLD, "reverse_proxy search.goreecloud.com:443"),
            ("reverse_proxy " + OLD, "reverse_proxy " + OLD + " {"),
        )
        for old, new in replacements:
            with self.subTest(changed_to=new):
                self.assertFalse(private_search_ingress_is_safe(SITE.decode().replace(old, new), OLD))

    def test_rejects_unknown_directives_and_duplicate_handlers(self):
        for injection in (
            "    route {\n        reverse_proxy " + OLD + "\n    }\n",
            "    log {\n        output stdout\n    }\n",
            "    @everyone remote_ip 0.0.0.0/0\n",
            "    handle @netbird_client {\n        reverse_proxy " + OLD + "\n    }\n",
            '    respond "Forbidden" 403\n',
        ):
            with self.subTest(injection=injection):
                altered = SITE.decode().replace("    @netbird_client remote_ip", injection + "    @netbird_client remote_ip")
                self.assertFalse(private_search_ingress_is_safe(altered, OLD))

    def test_rejects_security_header_override_and_broken_braces(self):
        template = (ROOT / "deploy/vps/Caddyfile.search").read_text(encoding="utf-8")
        self.assertFalse(private_search_ingress_is_safe(
            template.replace("Referrer-Policy no-referrer", 'Referrer-Policy unsafe-url'),
            "goreecloud-search-gateway:8080"))
        self.assertFalse(private_search_ingress_is_safe(template[:-2], "goreecloud-search-gateway:8080"))

    def test_bad_upstream_identity_rejected(self):
        for value in ("", "search.goreecloud.com:443", "example.org:8080",
                      "goreecloud-search-gateway:80", "goreecloud-search-gateway:8080/other"):
            with self.subTest(value=value):
                self.assertFalse(private_search_ingress_is_safe(SITE.decode(), value))

    def test_bounded_read_only_cli_reports_static_scope_and_no_config_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "Caddyfile"
            config.write_bytes(SITE)
            with patch("builtins.print") as output:
                self.assertEqual(0, guard.main([
                    "--caddyfile", str(config), "--expected-upstream", OLD]))
                result = json.loads(output.call_args.args[0])
                self.assertEqual("pass_static_only", result["status"])
                self.assertIs(result["runtime_verified"], False)
                self.assertNotIn("Caddyfile", output.call_args.args[0])
                self.assertNotIn("100.64.0.0/10", output.call_args.args[0])
                config.write_bytes(SITE.replace(b"100.64.0.0/10", b"0.0.0.0/0"))
                self.assertEqual(2, guard.main([
                    "--caddyfile", str(config), "--expected-upstream", OLD]))
                self.assertEqual("blocked_do_not_cutover",
                                 json.loads(output.call_args.args[0])["status"])


if __name__ == "__main__":
    unittest.main()
