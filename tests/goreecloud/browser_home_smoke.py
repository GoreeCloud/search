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
from tempfile import TemporaryDirectory
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
from native_search.index import SearchIndex  # noqa: E402

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


class SyntheticBrowserResultsCollection(SyntheticBrowserSearch):
    """Several deterministic synthetic results; never uses a provider."""
    def search(self):
        response = super().search()
        rows = []
        for i in range(1, 9):
            item = LegacyResult(
                url=f'https://example.org/goreecloud-test-{i}',
                title=f'Offline fixture result {i} — readable search result headline',
                content=(
                    'Synthetic result description with enough words to verify '
                    'the responsive column, line-height, and comfortable text '
                    'measure at desktop and phone widths. No external request.'
                ),
            )
            item.normalize_result_fields()
            rows.append(item)
        response.get_ordered_results = lambda: rows
        response.paging = True
        return response


class SyntheticBrowserImageResultsCollection(SyntheticBrowserSearch):
    """Real image-result templates backed only by inline PNG fixture bytes."""

    def search(self):
        import base64
        import struct
        import zlib

        response = super().search()

        def sample_png(index: int) -> str:
            # A locally generated 4x3 RGB PNG; never fetches a remote asset.
            color = ((index * 39) % 205 + 35, (index * 71) % 205 + 35, (index * 101) % 205 + 35)
            scanline = b"\x00" + bytes(color) * 4
            pixels = scanline * 3

            def chunk(kind: bytes, payload: bytes) -> bytes:
                return (struct.pack(">I", len(payload)) + kind + payload +
                        struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))

            png = (b"\x89PNG\r\n\x1a\n" +
                   chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 3, 8, 2, 0, 0, 0)) +
                   chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))
            return "data:image/png;base64," + base64.b64encode(png).decode("ascii")

        images = []
        for i in range(1, 13):
            img = sample_png(i)
            result = LegacyResult(
                title=f"Synthetic gallery image {i}",
                url=f"https://example.org/offline-image-{i}",
                template="images.html",
                img_src=img,
                thumbnail_src=img,
                resolution="4 x 3",
                img_format="PNG",
                engine="qwant images",
                category="images",
                source="Offline fixture",
                content="Locally generated pixels; no external image request.",
                author="GoreeCloud test",
                filesize="",
                formats=[],
            )
            result.normalize_result_fields()
            images.append(result)
        response.get_ordered_results = lambda: images
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
            # Privacy is a separate user-facing page: verify usable navigation
            # and keyboard focus at the same responsive viewports.
            driver.get(url + 'static/themes/simple/goreecloud/privacy.html')
            assert driver.find_element(By.CSS_SELECTOR, '#privacy-content h1').text.strip() == 'Privacy and sources'
            privacy_skip = driver.find_element(By.CSS_SELECTOR, 'a.skip-link[href="#privacy-content"]')
            driver.execute_script('arguments[0].focus()', privacy_skip)
            assert driver.execute_script('return document.activeElement === arguments[0]', privacy_skip)
            assert driver.execute_script(
                'return arguments[0].getBoundingClientRect().top >= 0', privacy_skip
            ), f'{label}: privacy skip link not visible when focused'
            privacy_skip.send_keys(Keys.ENTER)
            assert driver.current_url.endswith('#privacy-content'), f'{label}: skip target not navigable'
            privacy_overflow = driver.execute_script(
                'return document.documentElement.scrollWidth - document.documentElement.clientWidth'
            )
            assert privacy_overflow <= 2, f'{label}: privacy page overflow of {privacy_overflow}px'
            for nav_link in driver.find_elements(By.CSS_SELECTOR, 'header nav .links a'):
                assert nav_link.is_displayed(), f'{label}: privacy navigation link hidden'
            print(f'PASS privacy page responsive and keyboard navigation: {label}')
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
        # Provider choices belong to Preferences, not the home page.
        driver.get(url)
        assert not driver.find_elements(By.CSS_SELECTOR, '.goreecloud-home-source')
        assert not driver.find_elements(By.CSS_SELECTOR, '.goreecloud-preview-trigger')
        settings_link = driver.find_element(By.CSS_SELECTOR, 'a.goreecloud-settings-link')
        assert settings_link.get_attribute('href').endswith('/preferences')
        driver.get(url + 'preferences')
        options = driver.find_elements(By.CSS_SELECTOR, 'input[name="goreecloud_sources"]')
        assert sorted(option.get_attribute('value') for option in options) == ['all', 'bing', 'brave', 'duckduckgo', 'ecosia', 'google', 'qwant', 'startpage', 'working']
        brave_choice = driver.find_element(By.CSS_SELECTOR, 'input[name="goreecloud_sources"][value="brave"]')
        driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", brave_choice)
        brave_choice.click()
        save_button = driver.find_element(By.CSS_SELECTOR, 'form#search_form input[type="submit"]')
        driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", save_button)
        save_button.click()
        try:
            WebDriverWait(driver, 12).until(lambda page: page.current_url == url)
        except Exception:
            print('PREFERENCES SAVE DIAGNOSTIC', 'url=', driver.current_url,
                  'title=', driver.title,
                  'body_start=', driver.find_element(By.TAG_NAME, 'body').text[:190],
                  'post_metadata=', request_meta[-3:], flush=True)
            raise
        driver.get(url + 'preferences')
        selected = driver.find_element(By.CSS_SELECTOR, 'input[name="goreecloud_sources"][value="brave"]')
        assert selected.is_selected(), 'Saved Brave-only choice not persisted'
        all_choice = driver.find_element(By.CSS_SELECTOR, 'input[name="goreecloud_sources"][value="all"]')
        driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", all_choice)
        all_choice.click()
        save_button = driver.find_element(By.CSS_SELECTOR, 'form#search_form input[type="submit"]')
        driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", save_button)
        save_button.click()
        WebDriverWait(driver, 12).until(lambda page: page.current_url == url)
        # GoreeCloud-only Settings identity, responsive layout and real radio save.
        for width, height, label in ((1440, 900, 'desktop'), (390, 844, 'phone'), (320, 760, 'phone-small')):
            driver.set_window_size(width, height)
            driver.get(url + 'preferences')
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-preferences-intro h1').text == 'Settings'
            assert not driver.find_elements(By.CSS_SELECTOR, '#main_preferences > a img.logo')
            assert len(driver.find_elements(By.CSS_SELECTOR, 'input[name="goreecloud_sources"]')) == 8
            prefs_geom = driver.execute_script("""
              return {width:document.documentElement.clientWidth,
                scroll:document.documentElement.scrollWidth,
                title:document.querySelector('#main_preferences h1').getBoundingClientRect().width}
            """)
            assert prefs_geom['scroll'] <= prefs_geom['width'] + 1, (label, prefs_geom)
            if width == 320:
                # The visible word 'Interface' must remain intact at 320px.
                # A Range returns two rectangles when the browser splits it.
                interface_word_boxes = driver.execute_script("""
                  const label = document.getElementById('tab-label-ui');
                  const node = [...label.childNodes].find(n =>
                    n.nodeType === Node.TEXT_NODE && n.textContent.toLowerCase().includes('interface'));
                  if (!node) return -1;
                  const start = node.textContent.toLowerCase().indexOf('interface');
                  const range = document.createRange();
                  range.setStart(node, start);
                  range.setEnd(node, start + 'interface'.length);
                  return range.getClientRects().length;
                """)
                tab_geometry = driver.execute_script("""
                    const label = document.getElementById('tab-label-ui');
                    const style = getComputedStyle(label);
                    return {width: label.getBoundingClientRect().width,
                            clientWidth: label.clientWidth,
                            padding: style.padding, fontSize: style.fontSize,
                            fontWeight: style.fontWeight, letterSpacing: style.letterSpacing,
                            overflowWrap: style.overflowWrap,
                            parentColumns: getComputedStyle(label.parentElement).gridTemplateColumns};
                """)
                print('SETTINGS 320px label layout:', tab_geometry, flush=True)
                assert interface_word_boxes == 1, ('Settings tab word split across lines', interface_word_boxes)
            driver.save_screenshot(str(artifacts / f'settings-{label}.png'))
        driver.set_window_size(1440, 900)
        driver.get(url + 'preferences')
        driver.find_element(By.ID, 'tab-label-ui').click()
        assert driver.find_element(By.ID, 'tab-content-ui').is_displayed(), 'Interface settings tab cannot open'
        driver.find_element(By.ID, 'tab-label-general').click()
        assert driver.find_element(By.ID, 'tab-content-general').is_displayed(), 'General settings tab cannot reopen'
        print('PASS branded Settings layout and functioning tabs at desktop, phone and narrow phone')
        print('PASS no homepage source switches; Preferences persists chosen engines')
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
            details = driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-diagnostics')
            assert details.get_attribute('open') is None, 'Diagnostics must start collapsed'
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-state').is_displayed()
            assert not driver.find_elements(By.CSS_SELECTOR, '.goreecloud-source-switch')
            assert not driver.execute_script('return location.search')
            driver.save_screenshot(str(artifacts / 'phone-synthetic-results.png'))
            print('PASS results-first no-results state with collapsible provider diagnostics')
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic keyboard submission' + Keys.ENTER)
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                lambda page: page.current_url.endswith('/search'))
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-diagnostics')
            assert not driver.execute_script('return location.search'), 'Keyboard search leaked terms into URL'
            print('PASS keyboard Enter submits normal private POST search')
        # When a provider reports an error and results are empty, the user
        # explicitly retries the SAME source through native POST (no fallback).
        with patch('searx.search.SearchWithPlugins', side_effect=SyntheticBrowserFailedSearch) as failed:
            driver.set_window_size(390, 844)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic recoverable source error')
            driver.find_element(By.ID, 'send_search').click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                lambda page: page.current_url.endswith('/search') and
                bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-empty-retry button'))
            )
            retry = driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-retry button')
            assert retry.is_displayed() and retry.rect['height'] >= 44, 'Mobile error retry inaccessible'
            assert 'reported an error' in driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-state').text
            assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-empty-retry input[name="engines"]').get_attribute('value') == 'bing,brave,duckduckgo,ecosia,google,qwant,startpage'
            driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", retry)
            WebDriverWait(driver, 8).until(lambda page: page.execute_script(
                "const r=arguments[0].getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight;",
                retry
            ))
            retry.click()
            WebDriverWait(driver, 12).until(lambda page: failed.call_count == 2)
            assert driver.current_url.endswith('/search'), 'Retry left the private result route'
            assert not driver.execute_script('return location.search'), 'Retry leaked search terms into URL'
            assert driver.find_element(By.CSS_SELECTOR, 'form#search input[name="engines"]').get_attribute('value') == 'bing,brave,duckduckgo,ecosia,google,qwant,startpage'
        print('PASS mobile explicit same-source retry, no fallback, and POST URL privacy')

        # Layout contract with eight real template cards but NO provider
        # traffic. Check measured column geometry, typography and mobile
        # overflow; screenshots are disposable CI artifacts, not Glaze approval.
        with patch('searx.search.SearchWithPlugins', side_effect=SyntheticBrowserResultsCollection) as rich:
            driver.set_window_size(1440, 900)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('offline results layout fixture')
            driver.find_element(By.ID, 'send_search').click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                lambda page: page.current_url.endswith('/search') and
                len(page.find_elements(By.CSS_SELECTOR, '#urls article.result')) == 8
            )
            desktop_geometry = driver.execute_script("""
              const main=document.querySelector('#urls').getBoundingClientRect();
              const side=document.querySelector('#sidebar').getBoundingClientRect();
              const card=document.querySelector('#urls article.result').getBoundingClientRect();
              return { main:main.width, side:side.width, card:card.width,
                separate:main.right + 10 <= side.left,
                headline:parseFloat(getComputedStyle(document.querySelector('#urls article.result h3')).fontSize),
                heading:!!document.querySelector('.goreecloud-results-heading'),
                audit:!!document.querySelector('.goreecloud-source-diagnostics') };
            """)
            assert desktop_geometry['separate'], f'Results/sidebar overlap: {desktop_geometry}'
            assert desktop_geometry['main'] >= 590, f'Results too narrow: {desktop_geometry}'
            assert 230 <= desktop_geometry['side'] <= 330, desktop_geometry
            assert desktop_geometry['card'] >= 585, desktop_geometry
            assert desktop_geometry['headline'] >= 18, desktop_geometry
            assert desktop_geometry['heading'] and desktop_geometry['audit'], desktop_geometry
            assert not driver.execute_script('return location.search'), 'Query leaked into browser URL'
            driver.save_screenshot(str(artifacts / 'desktop-eight-result-layout.png'))

            driver.set_window_size(390, 844)
            WebDriverWait(driver, 5).until(
                lambda page: page.execute_script('return innerWidth <= 400')
            )
            mobile_geometry = driver.execute_script("""
              const main=document.querySelector('#urls').getBoundingClientRect();
              const side=document.querySelector('#sidebar').getBoundingClientRect();
              const card=document.querySelector('#urls article.result').getBoundingClientRect();
              return { viewport:innerWidth, client:document.documentElement.clientWidth,
                scroll:document.documentElement.scrollWidth, bodyScroll:document.body.scrollWidth,
                main:main.width, side:side.width, card:card.width,
                offending:[...document.querySelectorAll('body *')]
                  .filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.right>document.documentElement.clientWidth+1&&getComputedStyle(e).position!=='fixed'})
                  .slice(0,10).map(e=>({tag:e.tagName,id:e.id,cls:typeof e.className==='string'?e.className.slice(0,75):'',right:Math.round(e.getBoundingClientRect().right)})),
                sidebarBelow:side.top >= main.top + main.height - 4,
                choices:[...document.querySelectorAll('.goreecloud-provider-option')]
                  .map(e=>({y:Math.round(e.getBoundingClientRect().top),
                            h:e.getBoundingClientRect().height,
                            w:e.getBoundingClientRect().width})) };
            """)
            print('MOBILE RESULTS WIDTH:', mobile_geometry, flush=True)
            assert mobile_geometry['scroll'] <= mobile_geometry['client'] + 1, mobile_geometry
            assert mobile_geometry['main'] >= 310, mobile_geometry
            assert mobile_geometry['card'] >= 305, mobile_geometry
            assert mobile_geometry['sidebarBelow'], mobile_geometry
            driver.save_screenshot(str(artifacts / 'phone-eight-result-layout.png'))
            rich.assert_called_once()
        print('PASS desktop 2-column results and mobile stacked cards, 8 synthetic results, no provider traffic')


        # Render actual image-result cards (not generic search results), checking
        # the responsive thumbnail grid and upstream detail viewer without
        # real search or image network traffic.
        with patch('searx.search.SearchWithPlugins', SyntheticBrowserImageResultsCollection):
            for width, height, label in ((1440, 900, 'desktop'), (390, 844, 'phone'), (320, 760, 'phone-small')):
                driver.set_window_size(width, height)
                driver.get(url)
                driver.find_element(By.ID, 'q').send_keys('synthetic offline image gallery')
                driver.find_element(By.ID, 'send_search').click()
                WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                    lambda page: page.current_url.endswith('/search') and
                    bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-category-form'))
                )
                driver.find_element(By.XPATH,
                    "//nav[contains(@class,'goreecloud-category-tabs')]//button[normalize-space()='Images']").click()
                WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                    lambda page: len(page.find_elements(By.CSS_SELECTOR, '#urls.goreecloud-image-results article.result-images')) == 12
                )
                geometry = driver.execute_script("""
                    const root=document.querySelector('#urls');
                    const cards=[...root.querySelectorAll('article.result-images')];
                    const image=cards[0].querySelector('img.image_thumbnail');
                    const css=getComputedStyle(root);
                    const cr=cards.map(c=>c.getBoundingClientRect());
                    const widths=new Set(cr.map(r=>Math.round(r.left)));
                    return {display:css.display, columns:css.gridTemplateColumns.split(' ').length,
                        distinctX:widths.size, viewport:document.documentElement.clientWidth,
                        scroll:document.documentElement.scrollWidth,
                        cardWidth:cr[0].width, imageWidth:image.getBoundingClientRect().width,
                        inlineImages:cards.every(c=>c.querySelector('img.image_thumbnail').src.startsWith('data:image/png;base64,')),
                        tileTitles:cards.every(c=>!!c.querySelector('span.title')?.textContent?.trim()),
                        captionsBelow:cards.every(c=>{
                            let i=c.querySelector('img.image_thumbnail').getBoundingClientRect();
                            let t=c.querySelector('span.title').getBoundingClientRect();
                            let s=c.querySelector('span.source').getBoundingClientRect();
                            let card=c.getBoundingClientRect();
                            return t.top >= i.bottom-1 && s.top >= t.bottom-1 && card.bottom >= s.bottom-1;
                        }),
                        categoryTabsFit:(()=>{
                            const tabNav=document.querySelector('.goreecloud-category-tabs');
                            const r=tabNav.getBoundingClientRect();
                            const tabRects=[...tabNav.querySelectorAll('.goreecloud-category-tab')].map(t=>t.getBoundingClientRect());
                            return tabRects.length===4 && tabNav.scrollWidth<=tabNav.clientWidth+1 &&
                                tabRects.every(x=>x.left>=r.left-1 && x.right<=r.right+1);
                        })(),
                        badgesCompact:cards.every(c=>{
                            let b=c.querySelector('.image_resolution').getBoundingClientRect();
                            let i=c.querySelector('img.image_thumbnail').getBoundingClientRect();
                            return b.height <= 32 && b.top >= i.top && b.bottom <= i.bottom+1;
                        })};
                """)
                print('IMAGE GRID', label, geometry, flush=True)
                assert geometry['display'] == 'grid', (label, geometry)
                assert geometry['inlineImages'], (label, geometry)
                WebDriverWait(driver, 5).until(
                    lambda page: page.execute_script(
                        "return [...document.querySelectorAll('#urls article.result-images img.image_thumbnail')].slice(0,2).every(img => img.complete && img.naturalWidth > 0)"
                    )
                )
                assert geometry['tileTitles'], (label, geometry)
                assert geometry['captionsBelow'] and geometry['badgesCompact'], (label, geometry)
                if label != 'desktop':
                    assert geometry['categoryTabsFit'], (label, geometry)
                assert geometry['scroll'] <= geometry['viewport'] + 1, (label, geometry)
                assert geometry['cardWidth'] >= 120 and geometry['imageWidth'] >= 100, (label, geometry)
                if label == 'desktop':
                    assert geometry['distinctX'] >= 4, (label, geometry)
                else:
                    assert geometry['distinctX'] == 2, (label, geometry)
                driver.save_screenshot(str(artifacts / f'{label}-image-gallery.png'))
                first = driver.find_element(By.CSS_SELECTOR, '#urls article.result-images')
                first.find_element(By.CSS_SELECTOR, 'a').click()
                WebDriverWait(driver, 5).until(
                    lambda page: 'image-detail-open' in page.find_element(By.ID, 'results').get_attribute('class')
                )
                assert driver.current_url.endswith('#image-viewer'), 'Image viewer should open in page'
                assert not driver.execute_script('return location.search'), 'Image viewer leaked search query'
                driver.find_element(By.CSS_SELECTOR, '.result-images[data-vim-selected] .result-detail-close').click()
                WebDriverWait(driver, 5).until(
                    lambda page: 'image-detail-open' not in page.find_element(By.ID, 'results').get_attribute('class')
                )
        print('PASS desktop and phone image grid, 12 loaded offline PNGs, image details and POST privacy')

        # Category tabs must really submit POST, preserve the original query,
        # and never send it through the browser URL.
        with patch('searx.search.SearchWithPlugins', SyntheticBrowserResultsCollection):
            driver.set_window_size(1440, 900)
            driver.get(url)
            driver.find_element(By.ID, 'q').send_keys('synthetic category navigation')
            driver.find_element(By.ID, 'send_search').click()
            WebDriverWait(driver, 12).until(
                lambda page: len(page.find_elements(By.CSS_SELECTOR, '.goreecloud-category-form')) == 4
            )
            labels = [button.text.strip() for button in driver.find_elements(
                By.CSS_SELECTOR, '.goreecloud-category-tab')]
            assert labels == ['Web', 'Images', 'Videos', 'News'], labels
            driver.save_screenshot(str(artifacts / 'desktop-category-tabs.png'))
            driver.find_element(By.XPATH,
                "//nav[contains(@class,'goreecloud-category-tabs')]//button[normalize-space()='Images']").click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                lambda page: len(page.find_elements(
                    By.CSS_SELECTOR, '.goreecloud-category-tab[aria-current="page"]')) == 1
                and page.find_element(
                    By.CSS_SELECTOR, '.goreecloud-category-tab[aria-current="page"]').text.strip() == 'Images'
            )
            assert not driver.execute_script('return location.search'), 'Category switch leaked query'
            assert driver.find_element(By.CSS_SELECTOR, '#q').get_attribute('value') == 'synthetic category navigation'
            assert driver.find_element(By.CSS_SELECTOR,
                '.goreecloud-category-form input[name="engines"][value="brave.images,startpage images,qwant images,duckduckgo images,bing images,google images"]')
            driver.set_window_size(390, 844)
            driver.save_screenshot(str(artifacts / 'phone-category-tabs.png'))
            overflow = driver.execute_script(
                'return document.documentElement.scrollWidth - document.documentElement.clientWidth')
            assert overflow <= 1, f'Category tabs overflow phone width: {overflow}'
        print('PASS category tabs Web/Images/Videos/News, private POST navigation and phone overflow')


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
            warning = driver.find_element(By.CSS_SELECTOR, '.goreecloud-results-inline-note[role="status"]')
            assert warning.is_displayed(), 'Partial provider warning not displayed'
            assert driver.find_element(By.ID, 'engines_msg').find_element(
                By.CSS_SELECTOR, 'details'
            ).get_attribute('open') is not None, 'Provider error details were collapsed'
            assert driver.find_element(By.CSS_SELECTOR, '#urls').is_displayed()
            driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-diagnostics > summary').click()
            retry = driver.find_element(By.CSS_SELECTOR, '.goreecloud-partial-retry button')
            assert retry.is_displayed(), 'Partial retry action hidden'
            selected = driver.find_element(
                By.CSS_SELECTOR, '.goreecloud-partial-retry input[name="engines"]'
            ).get_attribute('value')
            assert selected == 'bing,brave,duckduckgo,ecosia,google,qwant,startpage', f'Partial retry selected unexpected sources: {selected}'
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
            driver.find_element(By.ID, 'send_search').click()
            WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                lambda page: page.current_url.endswith('/search') and
                bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-previous-results button'))
            )
            previous = driver.find_element(By.CSS_SELECTOR, '.goreecloud-previous-results button')
            assert previous.is_displayed() and previous.rect['height'] >= 44, 'Previous page touch action is too small'
            assert driver.find_element(By.CSS_SELECTOR,
                '.goreecloud-previous-results input[name="engines"]').get_attribute('value') == 'bing,brave,duckduckgo,ecosia,google,qwant,startpage'
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
                'form#search input[name="engines"]').get_attribute('value') == 'bing,brave,duckduckgo,ecosia,google,qwant,startpage'
        print('PASS phone previous-page POST recovery and exact saved-source continuity')

        # Exercise a synthetic denied URL without dispatching a search.
        driver.get(url + 'search?q=synthetic-private-smoke-fixture')
        assert driver.find_element(By.CSS_SELECTOR, '.goreecloud-policy-error[role=alert]').is_displayed()
        assert 'synthetic-private-smoke-fixture' not in driver.find_element(By.TAG_NAME, 'body').text
        assert driver.find_element(By.LINK_TEXT, 'Return to GoreeCloud Search').is_displayed()
        print('PASS accessible no-query-reflection policy error view')
        # Real browser click-through for the opt-in native Development source.
        # Uses a temporary synthetic GitHub-document index and no providers.
        with TemporaryDirectory(prefix='goreecloud-native-browser-') as native_dir:
            native_db = Path(native_dir) / 'approved.sqlite'
            with SearchIndex(native_db) as idx:
                idx.add(url='https://github.com/GoreeCloud/search/blob/' +
                        'a'*40 + '/docs/goreecloud/fixture.md',
                        title='GoreeCloud reviewed fixture',
                        body='GoreeCloud native search synthetic browser document')
            with patch.dict(os.environ, {'GOREECLOUD_NATIVE_SOURCE_ENABLED':'1',
                                          'GOREECLOUD_NATIVE_INDEX_PATH':str(native_db)}):
                for width, height, label in ((1440,900,'desktop'),(390,844,'phone'),(320,760,'phone-small')):
                    driver.set_window_size(width, height)
                    driver.get(url)
                    button = driver.find_element(By.CSS_SELECTOR, 'button[name="native_source"]')
                    assert button.is_displayed(), label
                    assert button.get_attribute('formmethod') == 'post'
                    driver.find_element(By.ID, 'q').send_keys('GoreeCloud')
                    driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", button)
                    WebDriverWait(driver, 5).until(lambda page: page.execute_script(
                        "const r=arguments[0].getBoundingClientRect();"
                        "const el=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);"
                        "return r.top>=0 && r.bottom<=innerHeight && arguments[0].contains(el);",
                        button))
                    print('NATIVE_VIEWPORT', label, driver.execute_script('return [innerWidth,innerHeight]'), flush=True)
                    button.click()
                    WebDriverWait(driver, 12).until(lambda page: page.current_url.endswith('/native-search'))
                    assert not driver.execute_script('return location.search'), label
                    hits = driver.find_elements(By.CSS_SELECTOR, '.goreecloud-native-hit')
                    assert len(hits) == 1, (label,len(hits))
                    assert 'GoreeCloud reviewed fixture' in hits[0].text
                    print(f'PASS native opt-in real-browser click {label}, no external provider')
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
