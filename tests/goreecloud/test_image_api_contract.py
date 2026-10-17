"""Run the image-only runtime in a separate process so legacy private-web
smoke tests retain their own default search profile and engine registry."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGE = ROOT / "configs/goreecloud/image-search-settings.yml"

RUNTIME = """
import json
from types import SimpleNamespace
from unittest.mock import patch
from searx.webapp import app, settings
from searx.engines import engines

assert settings['goreecloud']['image_search'] is True
assert settings['goreecloud']['private_search'] is False
assert set(engines) == {'brave.images', 'bing images', 'duckduckgo images'}, list(engines)
assert list(settings['categories_as_tabs']) == ['images']

class OfflineImages:
    def __init__(self, query, *args):
        self.query = query
    def search(self):
        return SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )

headers = {'X-Real-IP': '127.0.0.1'}
with app.test_client() as client, patch('searx.search.SearchWithPlugins', side_effect=OfflineImages) as dispatcher:
    valid = {'q': 'Samsung One UI', 'categories': 'images', 'format': 'json',
             'pageno': '1', 'safesearch': '1'}
    good = client.post('/search', data=valid, headers=headers)
    assert good.status_code == 200, (good.status_code, good.get_data(as_text=True)[:600])
    assert isinstance(good.json['results'], list)
    assert good.headers['Cache-Control'].startswith('private, no-store')
    good.close()
    assert dispatcher.called
    dispatcher.reset_mock()
    invalid = (
        ('get', '/search?q=private-term&categories=images&format=json', None, 405),
        ('post', '/search?q=leaked', valid, 405),
        ('post', '/search', {**valid, 'format': 'html'}, 406),
        ('post', '/search', {**valid, 'q': ''}, 400),
        ('post', '/search', {**valid, 'q': 'z'*181}, 413),
        ('post', '/search', {**valid, 'q': '!brimg widgets'}, 422),
        ('post', '/search', {**valid, 'categories': 'general'}, 422),
        ('post', '/search', {**valid, 'engines': 'google images'}, 422),
    )
    for method, url, form, expected in invalid:
        result = client.open(url, method=method.upper(), data=form, headers=headers)
        assert result.status_code == expected, (method, expected, result.status_code, result.get_data(as_text=True)[:400])
        assert 'no-store' in result.headers['Cache-Control']
        result.close()
    dispatcher.assert_not_called()
print('Image API HTTP contract passed without any provider requests.')
"""


class ImageApiRuntimeContractTests(unittest.TestCase):
    def test_image_api_isolation_post_and_failure_modes(self):
        env = os.environ.copy()
        env["SEARXNG_SETTINGS_PATH"] = str(IMAGE)
        env["SEARXNG_SECRET"] = "synthetic-image-api-test-only-secret-not-deployed"
        completed = subprocess.run(
            [sys.executable, "-c", RUNTIME], cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=55, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout[-1000:] + completed.stderr[-3000:])
        self.assertIn("Image API HTTP contract passed", completed.stdout)
