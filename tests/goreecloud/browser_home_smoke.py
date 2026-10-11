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
from selenium.webdriver.support.ui import WebDriverWait  # noqa: E402


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
            assert 'Brave Search' in driver.find_element(By.TAG_NAME, 'body').text
            assert 'Startpage' in driver.find_element(By.TAG_NAME, 'body').text
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
                "return [...document.styleSheets].some(s => s.href && s.href.includes('goreecloud-mockup.css'))"
            )
            site_header = driver.find_element(By.CSS_SELECTOR, '.goreecloud-site-header')
            site_footer = driver.find_element(By.CSS_SELECTOR, '.goreecloud-site-footer')
            hero_mark = driver.find_element(By.CSS_SELECTOR, '.goreecloud-mark-hero')
            why = driver.find_element(By.CSS_SELECTOR, '#why-goreecloud-search')
            search_box = driver.find_element(By.CSS_SELECTOR, '.goreecloud-hero .search_box')
            assert all(part.is_displayed() for part in (site_header, site_footer, hero_mark, why, search_box))
            assert len(driver.find_elements(By.CSS_SELECTOR, '.goreecloud-home-benefits li')) == 4
            assert hero_mark.rect['width'] >= 64, hero_mark.rect
            assert 260 <= search_box.rect['width'] <= 820, search_box.rect
            assert abs(hero_mark.rect['x'] + hero_mark.rect['width']/2 - width/2) < 30, 'Hero logo off center'
            assert why.rect['y'] > search_box.rect['y'], 'Mission statement above search'
            assert site_footer.rect['y'] > why.rect['y'], 'Footer above mission'
            if label == 'phone':
                assert not driver.find_element(By.CSS_SELECTOR, '.goreecloud-nav-secondary').is_displayed()
                assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-site-nav a[href*="github.com"]').is_displayed()
            else:
                assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-nav-secondary').is_displayed()
            print(f'LAYOUT {label}: logo={hero_mark.rect}; search={search_box.rect}; footer-y={site_footer.rect["y"]}')
            assert not driver.find_elements(By.CSS_SELECTOR, "link[type='application/opensearchdescription+xml']")
            spill = driver.execute_script(
                "return document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            if spill > 2:
                offscreen = driver.execute_script("""return [...document.querySelectorAll('*')].map(e => ({e, r:e.getBoundingClientRect()})).filter(o => o.r.width > 1 && (o.r.right > document.documentElement.clientWidth+2 || o.r.left < -2) && getComputedStyle(o.e).display !== 'none').slice(0,15).map(o => [o.e.tagName, String(o.e.className).slice(0,55), Math.round(o.r.left), Math.round(o.r.right)])""")
                print(f'OFFSCREEN {label}: {offscreen}', flush=True)
            assert spill <= 2, f"{label}: horizontal overflow of {spill}px"
            driver.save_screenshot(str(artifacts / f"{label}.png"))
            print(f"PASS {label} {width}x{height}; overflow={spill}px; POST and Glaze styles verified")
        # Official mockup moon button is an actual local appearance control.
        driver.set_window_size(390, 844)
        driver.get(url)
        theme_button = driver.find_element(By.CSS_SELECTOR, '.goreecloud-theme-toggle')
        theme_button.click()
        assert driver.execute_script("return document.documentElement.classList.contains('theme-dark')"), 'Dark toggle failed'
        assert theme_button.get_attribute('aria-label') == 'Switch to light mode'
        driver.save_screenshot(str(artifacts / 'phone-dark.png'))
        driver.refresh()
        assert driver.execute_script("return document.documentElement.classList.contains('theme-dark')"), 'Session appearance did not persist'
        driver.find_element(By.CSS_SELECTOR, '.goreecloud-theme-toggle').click()
        assert driver.execute_script("return document.documentElement.classList.contains('theme-light')"), 'Light toggle failed'
        print('PASS moon button toggles light/dark appearance for this browser tab')
        # Preview selected providers first, then explicitly continue to the
        # synthetic search. The preview must never create a provider executor.
        with patch('searx.search.SearchWithPlugins', side_effect=SyntheticBrowserSearch) as preview_search:
            driver.set_window_size(390, 844)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic private preflight')
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-preview-trigger').click()
            WebDriverWait(driver, 12).until(lambda page: page.current_url != url)
            assert driver.current_url.endswith('/preview'), driver.current_url
            assert not driver.execute_script('return location.search'), 'preview query entered URL'
            preview_heading = driver.find_element(By.CSS_SELECTOR, '#preview-heading')
            assert preview_heading.is_displayed()
            assert 'No search-provider requests have been sent' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-preview').text
            approved = driver.find_elements(By.CSS_SELECTOR, '.goreecloud-preview-single select[name=engines] option[value]:not([value=""])')
            assert sorted(option.get_attribute('value') for option in approved) == ['brave', 'startpage']
            preview_search.assert_not_called()
            driver.save_screenshot(str(artifacts / 'phone-source-preview.png'))
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-preview-continue').click()
            WebDriverWait(driver, 12).until(lambda page: page.current_url.endswith('/search'))
            assert driver.current_url.endswith('/search'), driver.current_url
            assert not driver.execute_script('return location.search'), 'continued query entered URL'
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').is_displayed()
            preview_search.assert_called_once()
            print('PASS private preview, no provider executor, explicit POST continuation and URL privacy')
        # Exercise a real browser POST through the real SearXNG query parser,
        # while replacing provider execution with a synthetic local result.
        with patch('searx.search.SearchWithPlugins', SyntheticBrowserSearch):
            driver.set_window_size(390, 844)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic no-network test')
            driver.find_element(By.ID, 'send_search').click()
            WebDriverWait(driver, 12).until(lambda page: page.current_url.endswith('/search'))
            assert driver.current_url.endswith('/search'), driver.current_url
            assert not driver.execute_script('return location.search'), 'search terms leaked into URL'
            summary = driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary')
            assert summary.is_displayed()
            assert '0 selected source(s) represented' in summary.text, summary.text
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-state').is_displayed()
            assert 'synthetic no-network test' not in driver.title, 'private query leaked into page title'
            driver.save_screenshot(str(artifacts / 'phone-synthetic-results.png'))
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary details summary').click()
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-refine-source button').click()
            WebDriverWait(driver, 12).until(lambda page: '1 source(s) selected' in page.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text)
            assert driver.current_url.endswith('/search'), driver.current_url
            assert not driver.execute_script('return location.search'), 'one-source query entered URL'
            assert '1 source(s) selected' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-switch form:nth-child(3) button').click()
            WebDriverWait(driver, 12).until(lambda page: bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-source-switch form:nth-child(3) button:disabled')))
            assert '1 source(s) selected' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-switch form:nth-child(1) button').click()
            WebDriverWait(driver, 12).until(lambda page: bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-source-switch form:nth-child(1) button:disabled')))
            assert '2 source(s) selected' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text
            assert not driver.execute_script('return location.search'), 'switching sources entered URL query'
            print('PASS mobile POST, one-source refinement, Startpage/Both switching and URL privacy')
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
