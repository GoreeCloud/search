"""Source-contract checks requiring only the Python standard library."""
from pathlib import Path
import re
import os
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "searx/templates/simple"
ASSETS = ROOT / "searx/static/themes/simple"

class GoreeCloudFoundationTests(unittest.TestCase):
    def test_glaze_assets_resolve_locally(self):
        base = (THEME / "base.html").read_text()
        self.assertIn("glaze/css/glaze-v1.4.1.css", base)
        self.assertIn("goreecloud-search.css", base)
        css_dir = ASSETS / "glaze/css"
        self.assertTrue((css_dir / "glaze-v1.4.1.css").is_file())
        for source in css_dir.glob("*.css"):
            for ref in re.findall(r'@import\s+url\(["\'](\./[^"\']+)["\']\)', source.read_text()):
                self.assertTrue((source.parent / ref).is_file(), (source, ref))
        self.assertTrue((ASSETS / "goreecloud-search.css").is_file())

    def test_interface_semantics(self):
        base = (THEME / "base.html").read_text()
        index = (THEME / "index.html").read_text()
        search = (THEME / "simple_search.html").read_text()
        self.assertIn('data-glaze-consumer="goreecloud-search"', base)
        self.assertIn('data-glaze-semantic-surface="protected"', base)
        self.assertIn("GoreeCloud", index)
        self.assertIn('for="q"', search)
        self.assertIn('id="q"', search)

    def test_private_profile_fails_closed_on_exposure(self):
        text = (ROOT / "configs/goreecloud/settings.yml").read_text()
        for expected in ['bind_address: "127.0.0.1"', 'public_instance: false',
                         'enable_metrics: false', 'autocomplete: ""', 'image_proxy: true',
                         'method: "POST"', 'query_in_title: false']:
            self.assertIn(expected, text)
        self.assertNotIn('secret_key:', text)
        self.assertIn("SEARXNG_SECRET", (ROOT / "README.md").read_text())

    def test_licensing_and_upstream_trace(self):
        self.assertTrue((ROOT / "LICENSE").is_file())
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", (ROOT / "LICENSE").read_text())
        self.assertIn("f4822b3fc46726bb259d14c6332b702c76b98f82", (ROOT / "UPSTREAM.md").read_text())

    def test_product_icon_has_no_remote_dependencies(self):
        icon = (ASSETS / "img/favicon.svg").read_text()
        self.assertIn("GoreeCloud Search", icon)
        self.assertIn("<svg", icon)
        self.assertNotIn("https://", icon)
        self.assertNotIn("<script", icon)
        base = (THEME / "base.html").read_text()
        self.assertNotIn("img/favicon.png", base)

    def test_private_launcher_refuses_missing_secret_and_public_overrides(self):
        script = str(ROOT / "scripts/run-private.sh")
        env = os.environ.copy()
        for k in ("SEARXNG_SECRET", "SEARXNG_BIND_ADDRESS", "SEARXNG_PUBLIC_INSTANCE"):
            env.pop(k, None)
        missing = subprocess.run(["bash", script], env=env, capture_output=True, text=True, timeout=4)
        self.assertEqual(64, missing.returncode)
        self.assertIn("SEARXNG_SECRET", missing.stderr)
        env["SEARXNG_SECRET"] = "a" * 40
        env["SEARXNG_BIND_ADDRESS"] = "0.0.0.0"
        exposed = subprocess.run(["bash", script], env=env, capture_output=True, text=True, timeout=4)
        self.assertEqual(64, exposed.returncode)
        self.assertIn("override refused", exposed.stderr)

    def test_local_privacy_notice(self):
        base = (THEME / "base.html").read_text()
        self.assertIn("goreecloud/privacy.html", base)
        notice = (ASSETS / "goreecloud/privacy.html").read_text()
        self.assertIn("Brave Search, Startpage, and Qwant", notice)
        self.assertIn("default sends search terms to all three", notice)
        self.assertIn("does not promise complete anonymity", notice)

    def test_accessibility_fallbacks(self):
        css = (ASSETS / "goreecloud-search.css").read_text()
        self.assertIn('background-image: none', css)
        self.assertIn('visibility: visible', css)
        for feature in ("focus-visible", "prefers-reduced-motion", "prefers-reduced-transparency",
                        "forced-colors: active", "max-width: 680px"):
            self.assertIn(feature, css)

if __name__ == "__main__":
    unittest.main()
