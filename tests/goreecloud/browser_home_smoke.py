"""Browser-only, no-provider home/search smoke. Requires Selenium and Chrome.

Uses an ephemeral loopback server and synthetic search response; never sends a
query to an actual upstream provider. Screenshot fixtures contain no user data.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import sys
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # direct-script CI launch from nested tests directory
os.environ["SEARXNG_SETTINGS_PATH"] = str(ROOT / "configs/goreecloud/settings.yml")
os.environ["SEARXNG_SECRET"] = secrets.token_hex(32)

from searx.webapp import app  # noqa: E402

from selenium import webdriver  # noqa: E402
from selenium.webdriver.chrome.options import Options  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402


class SyntheticBrowserSearch:
    """Return empty, local-only results after real form and query parsing."""
    def __init__(self, search_query, *args):
        self.search_query = search_query

    def search(self):
        return SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )


def main() -> None:
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,900")
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        url = f"http://127.0.0.1:{server.server_port}/"
        artifacts = ROOT / "artifacts" / "search-browser"
        artifacts.mkdir(parents=True, exist_ok=True)
        for width, height, label in ((1440, 900, "desktop"), (390, 844, "phone")):
            driver.set_window_size(width, height)
            driver.get(url)
            driver.save_screenshot(str(artifacts / f"{label}.png"))
            assert "GoreeCloud Search" in driver.title
            heading = driver.find_element(By.CSS_SELECTOR, "#main_index .title h1")
            heading_text = (heading.get_attribute("textContent") or "").strip()
            assert "GoreeCloud" in heading_text and "Search" in heading_text, heading_text
            assert heading.is_displayed(), f"{label}: GoreeCloud heading is hidden"
            assert driver.execute_script(
                "return getComputedStyle(document.querySelector('#main_index .index .title')).backgroundImage"
            ) == 'none', f"{label}: inherited upstream image logo is still visible"
            search = driver.find_element(By.CSS_SELECTOR, "form#search")
            assert search.get_attribute("method").lower() == "post"
            assert driver.find_element(By.CSS_SELECTOR, "[role=note].goreecloud-source-disclosure").is_displayed()
            assert driver.find_element(By.CSS_SELECTOR, "label[for=q]").text.strip() == "Search query"
            assert driver.execute_script(
                "return [...document.styleSheets].some(s => s.href && s.href.includes('goreecloud-search.css'))"
            )
            assert not driver.find_elements(By.CSS_SELECTOR, "link[type='application/opensearchdescription+xml']")
            spill = driver.execute_script(
                "return document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            assert spill <= 2, f"{label}: horizontal overflow of {spill}px"
            driver.save_screenshot(str(artifacts / f"{label}.png"))
            print(f"PASS {label} {width}x{height}; overflow={spill}px; POST and Glaze styles verified")
        # Preview selected providers first, then explicitly continue to the
        # synthetic search. The preview must never create a provider executor.
        with patch('searx.search.SearchWithPlugins', SyntheticBrowserSearch) as preview_search:
            driver.set_window_size(390, 844)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic private preflight')
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-preview-trigger').click()
            assert driver.current_url.endswith('/preview'), driver.current_url
            assert not driver.execute_script('return location.search'), 'preview query entered URL'
            preview_heading = driver.find_element(By.CSS_SELECTOR, '#preview-heading')
            assert preview_heading.is_displayed()
            assert 'No search-provider requests have been sent' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-preview').text
            preview_search.assert_not_called()
            driver.save_screenshot(str(artifacts / 'phone-source-preview.png'))
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-preview-continue').click()
            assert driver.current_url.endswith('/search'), driver.current_url
            assert not driver.execute_script('return location.search'), 'continued query entered URL'
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').is_displayed()
            print('PASS private preview, no provider executor, explicit POST continuation and URL privacy')
        # Exercise a real browser POST through the real SearXNG query parser,
        # while replacing provider execution with a synthetic local result.
        with patch('searx.search.SearchWithPlugins', SyntheticBrowserSearch):
            driver.set_window_size(390, 844)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic no-network test')
            driver.find_element(By.ID, 'send_search').click()
            assert driver.current_url.endswith('/search'), driver.current_url
            assert not driver.execute_script('return location.search'), 'search terms leaked into URL'
            summary = driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary')
            assert summary.is_displayed()
            assert '0 selected source(s) represented' in summary.text, summary.text
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-state').is_displayed()
            assert 'synthetic no-network test' not in driver.title, 'private query leaked into page title'
            driver.save_screenshot(str(artifacts / 'phone-synthetic-results.png'))
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-refine-source button').click()
            assert driver.current_url.endswith('/search'), driver.current_url
            assert not driver.execute_script('return location.search'), 'one-source query entered URL'
            assert '1 source(s) selected' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text
            print('PASS synthetic mobile POST, source-only refinement, empty-result recovery and URL privacy')
        # Exercise a synthetic denied URL without dispatching a search.
        driver.get(url + 'search?q=synthetic-private-smoke-fixture')
        assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-policy-error[role=alert]').is_displayed()
        assert 'synthetic-private-smoke-fixture' not in driver.find_element(By.TAG_NAME, 'body').text
        assert driver.find_element(By.LINK_TEXT, 'Return to GoreeCloud Search').is_displayed()
        print('PASS accessible no-query-reflection policy error view')
        # Verify the readable dark-mode token fallback without a remote asset.
        driver.execute_script("document.documentElement.classList.add('theme-dark')")
        bg = driver.execute_script("return getComputedStyle(document.body).backgroundColor")
        assert bg != "rgba(0, 0, 0, 0)", "dark-mode body must have an opaque background"
        print(f"PASS dark appearance background {bg}")
    finally:
        if driver is not None:
            driver.quit()
        server.shutdown()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
