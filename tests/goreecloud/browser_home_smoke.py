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
from flask import request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # direct-script CI launch from nested tests directory
os.environ["SEARXNG_SETTINGS_PATH"] = str(ROOT / "configs/goreecloud/settings.yml")
os.environ["SEARXNG_SECRET"] = secrets.token_hex(32)

from searx.webapp import app  # noqa: E402
from searx.result_types import LegacyResult  # noqa: E402

from selenium import webdriver  # noqa: E402
from selenium.webdriver.chrome.options import Options  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.common.keys import Keys  # noqa: E402
from selenium.webdriver.support.ui import WebDriverWait  # noqa: E402
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException  # noqa: E402


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


class SyntheticBrowserFailedSearch(SyntheticBrowserSearch):
    """Synthetic provider error without contacting an external provider."""

    def search(self):
        response = super().search()
        response.unresponsive_engines = [
            SimpleNamespace(engine='startpage', error_type='TimeoutException', suspended=False)
        ]
        return response

class SyntheticBrowserPartialSearch(SyntheticBrowserFailedSearch):
    """Show an offline fixture result plus one synthetic provider error."""

    def search(self):
        response = super().search()
        result = LegacyResult(
            url='https://example.org/synthetic-browser-partial',
            title='Synthetic browser result',
            content='Offline-only browser fixture; no provider contacted.',
        )
        result.normalize_result_fields()
        response.get_ordered_results = lambda: [result]
        return response


def main() -> None:
    # Record only request-boundary metadata from this synthetic browser fixture.
    # Never collect query text or request bodies in CI diagnostics.
    request_meta = []

    def note_boundary_context():
        if request.method == 'POST':
            request_meta.append((
                request.path, request.host, request.scheme,
                request.headers.get('Origin'), request.headers.get('Sec-Fetch-Site'),
                request.content_length,
            ))

    app.before_request_funcs.setdefault(None, []).insert(0, note_boundary_context)
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
        for width, height, label in ((1440, 900, "desktop"), (768, 900, "tablet"), (390, 844, "phone"), (320, 760, "phone-small")):
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
            assert driver.find_element(By.CSS_SELECTOR, 'form#search input#q').get_attribute('maxLength') == '512', 'Private query limit missing from browser input'
            assert driver.find_element(By.CSS_SELECTOR, "[role=note].goreecloud-source-disclosure").is_displayed()
            assert driver.find_element(By.CSS_SELECTOR, "label[for=q]").text.strip() == "Search query"
            assert driver.execute_script(
                "return [...document.styleSheets].some(s => s.href && s.href.includes('goreecloud-mockup.css'))"
            )
            site_header = driver.find_element(By.CSS_SELECTOR, '.goreecloud-site-header')
            site_footer = driver.find_element(By.CSS_SELECTOR, '.goreecloud-site-footer')
            hero_mark = driver.find_element(By.CSS_SELECTOR, '.goreecloud-mark-hero')
            artwork = hero_mark.find_element(By.CSS_SELECTOR, 'img')
            header_artwork = driver.find_element(By.CSS_SELECTOR, '.goreecloud-mark-small img')
            favicon = driver.find_element(By.CSS_SELECTOR, 'link[rel=icon]')
            assert int(artwork.get_attribute('naturalWidth')) > 0, 'Brand artwork failed to load'
            assert artwork.get_attribute('src') == header_artwork.get_attribute('src') == favicon.get_attribute('href'), 'Search brand assets disagree'
            why = driver.find_element(By.CSS_SELECTOR, '#why-goreecloud-search')
            search_box = driver.find_element(By.CSS_SELECTOR, '.goreecloud-hero .search_box')
            assert all(part.is_displayed() for part in (site_header, site_footer, hero_mark, why, search_box))
            assert len(driver.find_elements(By.CSS_SELECTOR, '.goreecloud-home-benefits li')) == 4
            assert hero_mark.rect['width'] >= 64, hero_mark.rect
            assert 260 <= search_box.rect['width'] <= 820, search_box.rect
            assert abs(hero_mark.rect['x'] + hero_mark.rect['width']/2 - width/2) < 30, 'Hero logo off center'
            assert why.rect['y'] > search_box.rect['y'], 'Mission statement above search'
            assert site_footer.rect['y'] > why.rect['y'], 'Footer above mission'
            if width <= 700:
                assert not driver.find_element(By.CSS_SELECTOR, '.goreecloud-nav-secondary').is_displayed()
                assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-site-nav a[href*="github.com"]').is_displayed()
            else:
                assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-nav-secondary').is_displayed()
            if width <= 360:
                narrow_github = driver.find_element(By.CSS_SELECTOR, '.goreecloud-site-nav a[aria-label="Open source on GitHub"]')
                assert narrow_github.rect['width'] >= 44, 'Source link touch area is too narrow'
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
            if label == 'desktop':
                skip = driver.find_element(By.CSS_SELECTOR, '.goreecloud-skip-link')
                driver.execute_script('arguments[0].focus()', skip)
                assert driver.execute_script('return document.activeElement === arguments[0]', skip)
                assert driver.execute_script('return arguments[0].getBoundingClientRect().top >= 0', skip), 'Keyboard skip link stayed offscreen'
                skip.send_keys(Keys.ENTER)
                assert driver.current_url.endswith('#goreecloud-content-start'), 'Keyboard skip did not reach content'
                print('PASS keyboard-accessible skip to content')
        # Official mockup moon button is an actual local appearance control.
        driver.set_window_size(390, 844)
        driver.get(url)
        theme_button = driver.find_element(By.CSS_SELECTOR, '.goreecloud-theme-toggle')
        assert theme_button.rect['width'] >= 44 and theme_button.rect['height'] >= 44, 'Theme touch target too small'
        theme_button.send_keys(Keys.SPACE)
        assert driver.execute_script("return document.documentElement.classList.contains('theme-dark')"), 'Dark toggle failed'
        assert theme_button.get_attribute('aria-label') == 'Switch to light mode'
        driver.save_screenshot(str(artifacts / 'phone-dark.png'))
        driver.refresh()
        assert driver.execute_script("return document.documentElement.classList.contains('theme-dark')"), 'Session appearance did not persist'
        driver.find_element(By.CSS_SELECTOR, '.goreecloud-theme-toggle').click()
        assert driver.execute_script("return document.documentElement.classList.contains('theme-light')"), 'Light toggle failed'
        print('PASS moon button toggles light/dark appearance for this browser tab')
        # The slash shortcut is an optional focus aid, not a query-submission action.
        driver.get(url)
        driver.find_element(By.TAG_NAME, 'body').send_keys('/')
        q_field = driver.find_element(By.ID, 'q')
        assert driver.execute_script('return document.activeElement === arguments[0]', q_field), 'Slash did not focus query input'
        q_field.send_keys('literal/segment')
        assert q_field.get_attribute('value') == 'literal/segment', 'Slash was intercepted while typing'
        assert not driver.execute_script('return location.search'), 'Keyboard shortcut leaked query into URL'
        print('PASS slash focuses search and does not intercept typing inside search')
        # Home quick actions carry their submitter engine field via native POST,
        # despite inherited SearXNG form-submission interception.
        with patch('searx.search.SearchWithPlugins', SyntheticBrowserSearch):
            for source in ('brave', 'startpage'):
                driver.get(url)
                driver.find_element(By.ID, 'q').send_keys('synthetic quick provider')
                driver.find_element(By.CSS_SELECTOR, f'.goreecloud-home-source[value="{source}"]').click()
                try:
                    WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                        lambda page: page.current_url.endswith('/search') and
                        '1 source(s) selected' in page.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text
                    )
                except Exception:
                    print('BROWSER BOUNDARY DIAGNOSTIC:', source,
                          'url=', driver.current_url,
                          'title=', driver.title,
                          'page_head=', driver.find_element(By.TAG_NAME, 'body').text[:220],
                          'requests=', request_meta[-5:], flush=True)
                    raise
                selected = driver.find_element(By.CSS_SELECTOR, 'form#search input[name="engines"]')
                assert selected.get_attribute('value') == source, f'{source}: quick provider selection lost'
                assert not driver.execute_script('return location.search'), 'Provider shortcut leaked query in URL'
        print('PASS homepage provider shortcuts retain POST-only single-source selection')
        # Preview selected providers first, then explicitly continue to the
        # synthetic search. The preview must never create a provider executor.
        with patch('searx.search.SearchWithPlugins', side_effect=SyntheticBrowserSearch) as preview_search:
            driver.set_window_size(390, 844)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic private preflight')
            preview_action = driver.find_element(By.CSS_SELECTOR, '.goreecloud-preview-trigger')
            assert preview_action.rect['height'] >= 44, 'Preview touch target too small'
            driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", preview_action)
            WebDriverWait(driver, 8).until(lambda page: page.execute_script(
                "const r=arguments[0].getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight;",
                preview_action
            ))
            preview_action.click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(lambda page: page.current_url != url)
            assert driver.current_url.endswith('/preview'), driver.current_url
            assert not driver.execute_script('return location.search'), 'preview query entered URL'
            preview_heading = driver.find_element(By.CSS_SELECTOR, '#preview-heading')
            assert preview_heading.is_displayed()
            assert 'No search-provider requests have been sent' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-preview').text
            approved = driver.find_elements(By.CSS_SELECTOR, '.goreecloud-preview-single select[name=engines] option[value]:not([value=""])')
            assert sorted(option.get_attribute('value') for option in approved) == ['brave', 'startpage']
            preview_search.assert_not_called()
            driver.save_screenshot(str(artifacts / 'phone-source-preview.png'))
            assert 'Startpage availability' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-startpage-note').text
            continue_button = driver.find_element(By.CSS_SELECTOR, '.goreecloud-preview-continue')
            driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", continue_button)
            WebDriverWait(driver, 8).until(lambda page: page.execute_script(
                "const rect=arguments[0].getBoundingClientRect(); return rect.top >= 0 && rect.bottom <= innerHeight;", continue_button
            ))
            continue_button.click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(lambda page: page.current_url.endswith('/search'))
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
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(lambda page: page.current_url.endswith('/search'))
            assert driver.current_url.endswith('/search'), driver.current_url
            assert not driver.execute_script('return location.search'), 'search terms leaked into URL'
            summary = driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary')
            assert summary.is_displayed()
            assert '0 selected source(s) represented' in summary.text, summary.text
            assert not driver.find_element(By.ID, 'search_logo').is_displayed(), 'Duplicate app logo in results header'
            assert driver.find_element(By.CSS_SELECTOR, '#main_results .search_box').rect['width'] >= 300
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-state').is_displayed()
            assert 'synthetic no-network test' not in driver.title, 'private query leaked into page title'
            driver.save_screenshot(str(artifacts / 'phone-synthetic-results.png'))
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary details summary').click()
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-refine-source button').click()
            # A just-replaced results document can briefly invalidate Selenium's
            # DevTools node ID before the settled page can be read.
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException, WebDriverException)).until(
                lambda page: '1 source(s) selected' in page.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text
            )
            assert driver.current_url.endswith('/search'), driver.current_url
            assert not driver.execute_script('return location.search'), 'one-source query entered URL'
            assert '1 source(s) selected' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text
            switch_startpage = driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-switch form:nth-child(3) button')
            driver.execute_script("arguments[0].scrollIntoView({block:'center'})", switch_startpage)
            switch_startpage.click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(lambda page: bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-source-switch form:nth-child(3) button:disabled')))
            assert '1 source(s) selected' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text
            switch_both = driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-switch form:nth-child(1) button')
            driver.execute_script("arguments[0].scrollIntoView({block:'center'})", switch_both)
            switch_both.click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(lambda page: bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-source-switch form:nth-child(1) button:disabled')))
            assert '2 source(s) selected' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').text
            assert not driver.execute_script('return location.search'), 'switching sources entered URL query'
            print('PASS mobile POST, one-source refinement, Startpage/Both switching and URL privacy')
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic keyboard submission' + Keys.ENTER)
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(lambda page: page.current_url.endswith('/search'))
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-summary').is_displayed()
            assert not driver.execute_script('return location.search'), 'Keyboard search leaked terms into URL'
            print('PASS keyboard Enter submits normal private POST search')
        # When a provider reports an error and results are empty, the user
        # explicitly retries the SAME source through native POST (no fallback).
        with patch('searx.search.SearchWithPlugins', side_effect=SyntheticBrowserFailedSearch) as failed:
            driver.set_window_size(390, 844)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic recoverable source error')
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-home-source[value="startpage"]').click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                lambda page: page.current_url.endswith('/search') and
                bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-empty-retry button'))
            )
            retry = driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-retry button')
            assert retry.is_displayed() and retry.rect['height'] >= 44, 'Mobile error retry inaccessible'
            assert 'reported an error' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-state').text
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-retry input[name="engines"]').get_attribute('value') == 'startpage'
            driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", retry)
            WebDriverWait(driver, 8).until(lambda page: page.execute_script(
                "const r=arguments[0].getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight;",
                retry
            ))
            retry.click()
            WebDriverWait(driver, 12).until(lambda page: failed.call_count == 2)
            assert driver.current_url.endswith('/search'), 'Retry left the private result route'
            assert not driver.execute_script('return location.search'), 'Retry leaked search terms into URL'
            assert driver.find_element(By.CSS_SELECTOR, 'form#search input[name="engines"]').get_attribute('value') == 'startpage'
        print('PASS mobile explicit same-source retry, no fallback, and POST URL privacy')

        # A partial provider failure offers a deliberate POST retry on a
        # populated results page, without switching to an unselected source.
        with patch('searx.search.SearchWithPlugins', side_effect=SyntheticBrowserPartialSearch) as partial:
            driver.set_window_size(1440, 900)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic browser partial failure')
            driver.find_element(By.ID, 'send_search').click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                lambda page: page.current_url.endswith('/search') and
                bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-partial-retry button'))
            )
            warning = driver.find_element(By.CSS_SELECTOR, '.goreecloud-partial-results[role="status"]')
            assert warning.is_displayed(), 'Partial provider warning not displayed'
            assert driver.find_element(By.ID, 'engines_msg').find_element(
                By.CSS_SELECTOR, 'details'
            ).get_attribute('open') is not None, 'Provider error details were collapsed'
            assert driver.find_element(By.CSS_SELECTOR, '#urls').is_displayed()
            retry = driver.find_element(By.CSS_SELECTOR, '.goreecloud-partial-retry button')
            assert retry.is_displayed(), 'Partial retry action hidden'
            selected = driver.find_element(
                By.CSS_SELECTOR, '.goreecloud-partial-retry input[name="engines"]'
            ).get_attribute('value')
            assert selected == 'brave,startpage', f'Partial retry selected unexpected sources: {selected}'
            assert not driver.execute_script('return location.search'), 'Partial-result search leaked query'
            driver.save_screenshot(str(artifacts / 'desktop-partial-retry.png'))
            driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", retry)
            retry.click()
            WebDriverWait(driver, 12).until(lambda page: partial.call_count == 2)
            assert driver.current_url.endswith('/search'), 'Partial retry left private results route'
            assert not driver.execute_script('return location.search'), 'Partial retry leaked query into URL'
            assert driver.find_element(
                By.CSS_SELECTOR, '.goreecloud-partial-retry input[name="engines"]'
            ).get_attribute('value') == selected
        print('PASS desktop partial-provider warning and explicit same-source retry')

        # The empty later-page recovery is a real browser form POST; it
        # decrements the page without browser Back or URL query parameters.
        with patch('searx.search.SearchWithPlugins', side_effect=SyntheticBrowserSearch) as pages:
            driver.set_window_size(390, 844)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic browser previous page')
            driver.execute_script("""
                const form = document.querySelector('form#search');
                const p = document.createElement('input');
                p.type = 'hidden';
                p.name = 'pageno';
                p.value = '2';
                form.appendChild(p);
            """)
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-home-source[value="brave"]').click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                lambda page: page.current_url.endswith('/search') and
                bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-previous-results button'))
            )
            previous = driver.find_element(By.CSS_SELECTOR, '.goreecloud-previous-results button')
            assert previous.is_displayed() and previous.rect['height'] >= 44, 'Previous page touch action is too small'
            assert driver.find_element(By.CSS_SELECTOR,
                '.goreecloud-previous-results input[name="engines"]').get_attribute('value') == 'brave'
            assert driver.find_element(By.CSS_SELECTOR,
                '.goreecloud-previous-results input[name="pageno"]').get_attribute('value') == '1'
            assert not driver.execute_script('return location.search'), 'Later-page query entered URL'
            driver.save_screenshot(str(artifacts / 'phone-previous-results.png'))
            driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", previous)
            previous.click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                lambda page: pages.call_count == 2 and
                'No results found' in page.find_element(By.CSS_SELECTOR, '.goreecloud-empty-state').text
            )
            assert driver.current_url.endswith('/search')
            assert not driver.execute_script('return location.search'), 'Previous page leaked query into URL'
            assert not driver.find_elements(By.CSS_SELECTOR, '.goreecloud-previous-results')
            assert driver.find_element(By.CSS_SELECTOR,
                'form#search input[name="engines"]').get_attribute('value') == 'brave'
        print('PASS phone previous-page POST recovery and exact Brave provider continuity')

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
