"""Isolated, no-query-dispatch smoke checks for the GoreeCloud local interface."""
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("SEARXNG_SETTINGS_PATH", str(ROOT / "configs/goreecloud/settings.yml"))
# Throwaway test fixture only; never usable as a deployed secret.
os.environ.setdefault("SEARXNG_SECRET", "goreecloud-runtime-smoke-test-only-secret-0000")

from searx.webapp import app, settings  # noqa: E402


class PrivateRuntimeSmokeTests(unittest.TestCase):
    def test_config_runtime_privacy_defaults(self):
        self.assertEqual("GoreeCloud Search", settings["general"]["instance_name"])
        self.assertEqual("127.0.0.1", settings["server"]["bind_address"])
        self.assertIs(settings["server"]["public_instance"], False)
        self.assertEqual("POST", settings["server"]["method"])
        self.assertIs(settings["server"]["image_proxy"], True)
        self.assertIs(settings["general"]["enable_metrics"], False)
        self.assertEqual("", settings["search"]["autocomplete"])
        names = {engine['name'] for engine in settings['engines']}
        self.assertNotIn('ahmia', names)
        self.assertNotIn('torch', names)

    def test_home_and_local_assets_are_served(self):
        paths = {
            "/": "text/html",
            "/static/themes/simple/goreecloud-search.css": "text/css",
            "/static/themes/simple/glaze/css/glaze-v1.4.1.css": "text/css",
            "/static/themes/simple/goreecloud/privacy.html": "text/html",
        }
        with app.test_client() as client:
            for path, content_type in paths.items():
                response = client.get(path, headers={"X-Real-IP": "127.0.0.1"})
                try:
                    self.assertEqual(response.status_code, 200, path)
                    self.assertIn(content_type, response.content_type, path)
                    if path == "/":
                        self.assertIn(b"GoreeCloud", response.data)
                        self.assertIn(b'method="POST"', response.data)
                finally:
                    response.close()


if __name__ == "__main__":
    unittest.main()
