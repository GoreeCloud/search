"""Browser-only, no-provider home/search smoke. Requires Selenium and Chrome.

Uses an ephemeral loopback server and synthetic search response; never sends a
query to an actual upstream provider. Screenshot fixtures contain no user data.
"""
from __future__ import annotations

import os
import json
from collections import Counter
from pathlib import Path
import secrets
import sys
from threading import Lock, Thread
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from werkzeug.serving import make_server
from flask import Response, abort, request

from browser_image_fixtures import (IMAGE_GALLERY_COUNT, IMAGE_FIXTURE_ORIGIN,
                                    image_fixture_index, synthetic_image_png)

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


class SyntheticBrowserFailedImageSearch(SyntheticBrowserSearch):
    """An Images provider failed; test the truthful no-image layout offline."""

    def search(self):
        response = super().search()
        response.unresponsive_engines = [
            SimpleNamespace(engine='startpage images', error_type='TimeoutException', suspended=False)
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
    """Image cards with signed same-origin proxy URLs, NEVER external fetches."""

    def search(self):
        response = super().search()

        images = []
        for i in range(1, IMAGE_GALLERY_COUNT + 1):
            # The browser receives only signed /image_proxy URLs; a temporary
            # Flask view below returns the local pixels, without outbound I/O.
            img = f'{IMAGE_FIXTURE_ORIGIN}{i:02d}.png'
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


def assert_gc_search_controls(driver, context: str) -> None:
    """Computed browser acceptance for both private home/results search forms."""
    geometry = driver.execute_script(r"""
        const root = document.documentElement;
        const field = document.querySelector('form#search .search_box');
        const query = document.querySelector('form#search #q');
        const clear = document.querySelector('form#search #clear_search');
        const submit = document.querySelector('form#search #send_search');
        const r = node => node.getBoundingClientRect();
        const luminance = cssColor => {
            const rgb = cssColor.match(/[\d.]+/g).slice(0, 3).map(v => Number(v) / 255);
            const linear = rgb.map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
        };
        const foreground = luminance(getComputedStyle(query, '::placeholder').color);
        const background = luminance(getComputedStyle(field).backgroundColor);
        return {
            consumer: root.getAttribute('data-gc-consumer'),
            role: document.querySelector('form#search').getAttribute('role'),
            accessibleQuery: !!document.querySelector('label[for="q"]'),
            accessibleClear: !!clear.getAttribute('aria-label'),
            accessibleSubmit: !!submit.getAttribute('aria-label'),
            field: {left:r(field).left, right:r(field).right, height:r(field).height},
            query: {width:r(query).width},
            clear: {left:r(clear).left, right:r(clear).right, width:r(clear).width, height:r(clear).height},
            submit: {left:r(submit).left, right:r(submit).right, width:r(submit).width, height:r(submit).height},
            placeholderContrast: (Math.max(foreground, background) + 0.05) /
                (Math.min(foreground, background) + 0.05),
            viewport: root.clientWidth,
            overflow: root.scrollWidth - root.clientWidth,
        };
    """)
    assert geometry['consumer'] == 'goreecloud-search', (context, geometry)
    assert geometry['role'] == 'search', (context, geometry)
    assert all(geometry[name] for name in ('accessibleQuery', 'accessibleClear', 'accessibleSubmit')), (context, geometry)
    assert geometry['field']['height'] >= 48, (context, geometry)
    assert geometry['query']['width'] >= 75, (context, geometry)
    assert geometry['placeholderContrast'] >= 4.5, (context, geometry)
    for control in ('clear', 'submit'):
        measured = geometry[control]
        assert measured['width'] >= 44 and measured['height'] >= 44, (context, geometry)
        assert measured['left'] >= geometry['field']['left'] - 2, (context, geometry)
        assert measured['right'] <= geometry['field']['right'] + 2, (context, geometry)
    assert geometry['overflow'] <= 2, (context, geometry)

    # Keyboard/programmatic focus is perceptible on the entire field while the
    # individual actionable buttons retain their own visible focus indicator.
    for control in ('q', 'clear_search', 'send_search'):
        element = driver.find_element(By.CSS_SELECTOR, f'form#search #{control}')
        focus = driver.execute_script("""
            arguments[0].focus();
            const field = document.querySelector('form#search .search_box');
            const outline = getComputedStyle(field);
            const token = getComputedStyle(document.documentElement).getPropertyValue('--gc-v1-color-focus-ring').trim();
            const probe = document.createElement('span');
            probe.style.color = 'var(--gc-v1-color-focus-ring)';
            document.body.appendChild(probe);
            const expected = getComputedStyle(probe).color;
            probe.remove();
            return {
                active: document.activeElement === arguments[0],
                style: outline.outlineStyle,
                width: parseFloat(outline.outlineWidth),
                color: outline.outlineColor,
                expected, token,
            };
        """, element)
        assert focus['active'] and focus['style'] == 'solid', (context, control, focus)
        assert focus['width'] >= 3 and focus['color'] == focus['expected'], (context, control, focus)
        assert focus['token'], (context, control, focus)


def assert_gc_search_forced_colors(driver, context: str) -> None:
    """Chrome's actual forced-colors media emulation, not a CSS text check."""
    driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
        'features': [{'name': 'forced-colors', 'value': 'active'}],
    })
    try:
        result = driver.execute_script("""
            const field = document.querySelector('form#search .search_box');
            const query = document.querySelector('form#search #q');
            const submit = document.querySelector('form#search #send_search');
            query.focus();
            const probe = document.createElement('span');
            probe.style.cssText = 'color:CanvasText;background:ButtonFace;outline:3px solid Highlight';
            document.body.appendChild(probe);
            const expected = getComputedStyle(probe);
            const colors = {
                canvasText: expected.color,
                buttonFace: expected.backgroundColor,
                highlight: expected.outlineColor,
            };
            probe.remove();
            return {
                enabled: matchMedia('(forced-colors: active)').matches,
                fieldShadow: getComputedStyle(field).boxShadow,
                fieldBorder: getComputedStyle(field).borderStyle,
                focusColor: getComputedStyle(field).outlineColor,
                queryColor: getComputedStyle(query).color,
                buttonColor: getComputedStyle(submit).backgroundColor,
                colors,
            };
        """)
        assert result['enabled'], (context, result)
        assert result['fieldShadow'] == 'none' and result['fieldBorder'] == 'solid', (context, result)
        assert result['focusColor'] == result['colors']['highlight'], (context, result)
        assert result['queryColor'] == result['colors']['canvasText'], (context, result)
        assert result['buttonColor'] == result['colors']['buttonFace'], (context, result)
    finally:
        driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': []})


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
        # Fail closed if a gallery regression bypasses /image_proxy: synthetic
        # remote-looking fixture origins are blocked at the browser boundary.
        driver.execute_cdp_cmd('Network.enable', {})
        driver.execute_cdp_cmd('Network.setBlockedURLs', {
            'urls': [f'{IMAGE_FIXTURE_ORIGIN}*'],
        })
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
            assert driver.execute_script(
                "return [...document.styleSheets].some(s => s.href && s.href.includes('gc-ui/css/gc.v1.generated.css'))"
            ), f"{label}: pinned local GC UI Foundations CSS did not load"
            gc_geometry = driver.execute_script("""
                const computed = getComputedStyle(document.documentElement);
                return [
                    computed.getPropertyValue('--gc-v1-foundation-radius-md').trim(),
                    computed.getPropertyValue('--gc-v1-foundation-target-comfortable').trim(),
                    computed.getPropertyValue('--gc-v1-component-focus-width').trim()
                ];
            """)
            assert gc_geometry == ['18px', '44px', '3px'], f"{label}: GC UI Foundations token contract failed: {gc_geometry}"
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
            assert_gc_search_controls(driver, f'home-{label}')
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
            print(f"PASS {label} {width}x{height}; overflow={spill}px; POST and local GC UI Foundations geometry verified (legacy UI remains)")
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
        assert driver.execute_script("return document.documentElement.getAttribute('data-gc-mode')") == 'dark', 'GC UI dark mode not synchronized'
        assert driver.execute_script("return getComputedStyle(document.documentElement).getPropertyValue('--gc-v1-color-focus-ring').trim()") == '#D8D2FF', 'GC UI dark semantic focus token not active'
        assert theme_button.get_attribute('aria-label') == 'Switch to light mode'
        assert theme_button.get_attribute('aria-pressed') == 'true', 'Dark toggle ARIA state not synchronized'
        assert_gc_search_controls(driver, 'home-dark')
        driver.save_screenshot(str(artifacts / 'phone-dark.png'))
        driver.refresh()
        assert driver.execute_script("return document.documentElement.classList.contains('theme-dark')"), 'Session appearance did not persist'
        assert driver.execute_script("return document.documentElement.getAttribute('data-gc-mode')") == 'dark', 'GC UI session dark mode lost'
        driver.find_element(By.CSS_SELECTOR, '.goreecloud-theme-toggle').click()
        assert driver.execute_script("return document.documentElement.classList.contains('theme-light')"), 'Light toggle failed'
        assert driver.execute_script("return document.documentElement.getAttribute('data-gc-mode')") == 'light', 'GC UI light mode not synchronized'
        assert driver.execute_script("return getComputedStyle(document.documentElement).getPropertyValue('--gc-v1-color-focus-ring').trim()") == '#4132B3', 'GC UI light semantic focus token not active'
        assert_gc_search_controls(driver, 'home-light')
        print('PASS moon button toggles light/dark appearance for this browser tab')
        assert_gc_search_forced_colors(driver, 'home-forced-colors')
        print('PASS homepage field, clear/search targets, visible focus and forced colors')
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
            assert len(driver.find_elements(By.CSS_SELECTOR, 'input[name="goreecloud_sources"]')) == 9
            prefs_geom = driver.execute_script("""
              const root = document.documentElement;
              const radio = document.querySelector('#tab-ui');
              const label = document.querySelector('#tab-label-ui');
              const tabs = document.querySelector('#search_form > .tabs');
              const source = document.querySelector('#search_form .goreecloud-provider-option input[name="goreecloud_sources"]');
              const language = document.querySelector('#search_form select[name="language"]');
              const save = document.querySelector('.goreecloud-preferences-actions > input[type="submit"]');
              const token = getComputedStyle(root).getPropertyValue('--gc-v1-foundation-target-comfortable').trim();
              return {consumer: root.getAttribute('data-gc-consumer'),
                token, tabHeight: label.getBoundingClientRect().height,
                tabRelation: label.control === radio && tabs.getAttribute('role') === 'tablist',
                tabPanel: !!document.querySelector('#tab-content-ui[role="tabpanel"]'),
                fieldToken: getComputedStyle(root).getPropertyValue('--gc-v1-component-field-height').trim(),
                buttonToken: getComputedStyle(root).getPropertyValue('--gc-v1-component-button-height-medium').trim(),
                sourceLabelHeight: source?.closest('label')?.getBoundingClientRect().height ?? 0,
                sourceLabelAccessible: source?.closest('label')?.textContent.trim().length > 0,
                languageHeight: language?.getBoundingClientRect().height ?? 0,
                languageLabelled: !!language?.getAttribute('aria-labelledby'),
                saveHeight: save?.getBoundingClientRect().height ?? 0,
                width:document.documentElement.clientWidth,
                scroll:document.documentElement.scrollWidth,
                title:document.querySelector('#main_preferences h1').getBoundingClientRect().width}
            """)
            assert prefs_geom['consumer'] == 'goreecloud-search', (label, prefs_geom)
            assert prefs_geom['token'] == '44px' and prefs_geom['tabHeight'] >= 44, (label, prefs_geom)
            assert prefs_geom['tabRelation'] and prefs_geom['tabPanel'], (label, prefs_geom)
            assert prefs_geom['fieldToken'] == '48px' and prefs_geom['languageHeight'] >= 48, (label, prefs_geom)
            assert prefs_geom['buttonToken'] == '44px' and prefs_geom['saveHeight'] >= 44, (label, prefs_geom)
            assert prefs_geom['sourceLabelAccessible'] and prefs_geom['sourceLabelHeight'] >= 44, (label, prefs_geom)
            assert prefs_geom['languageLabelled'], (label, prefs_geom)
            assert prefs_geom['scroll'] <= prefs_geom['width'] + 1, (label, prefs_geom)
            keyboard_source = driver.find_element(By.CSS_SELECTOR, 'input[name="goreecloud_sources"][value="working"]')
            keyboard_source.send_keys(Keys.SPACE)
            source_focus = driver.execute_script("""
              const input=arguments[0];
              const label=input.closest('.goreecloud-provider-option');
              const style=getComputedStyle(label);
              return {focused:document.activeElement===input, visible:input.matches(':focus-visible'),
                outline:style.outlineStyle, width:parseFloat(style.outlineWidth)};
            """, keyboard_source)
            assert source_focus['focused'] and source_focus['visible'], (label, source_focus)
            assert source_focus['outline'] == 'solid' and source_focus['width'] >= 3, (label, source_focus)
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
            assert_gc_search_controls(driver, 'results-phone')
            assert_gc_search_forced_colors(driver, 'results-phone-forced-colors')
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
            # Keyboard users must see GC UI's visible focus and may retry via
            # the same native POST without a pointer or changing providers.
            retry.send_keys(Keys.ARROW_LEFT)
            retry_focus = driver.execute_script("""
              const retry=arguments[0];
              const css=getComputedStyle(retry);
              const root=document.documentElement;
              return {visible:retry.matches(':focus-visible'), focused:document.activeElement===retry,
                outline:css.outlineStyle, outlineWidth:parseFloat(css.outlineWidth),
                height:retry.getBoundingClientRect().height,
                buttonToken:getComputedStyle(root).getPropertyValue('--gc-v1-component-button-height-medium').trim(),
                method:retry.form?.method, type:retry.type,
                viewport:root.clientWidth, scroll:root.scrollWidth};
            """, retry)
            assert retry_focus['visible'] and retry_focus['focused'], retry_focus
            assert retry_focus['outline'] == 'solid' and retry_focus['outlineWidth'] >= 3, retry_focus
            assert retry_focus['height'] >= 44 and retry_focus['buttonToken'] == '44px', retry_focus
            assert retry_focus['method'] == 'post' and retry_focus['type'] == 'submit', retry_focus
            assert retry_focus['scroll'] <= retry_focus['viewport'] + 1, retry_focus
            retry.send_keys(Keys.SPACE)
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


        # Accept the actual browser-rendered Images route and its same-origin
        # signed /image_proxy flow. This temporary view serves synthetic PNGs;
        # neither Chrome nor SearXNG contacts a live search/image provider.
        proxy_seen = Counter()
        proxy_lock = Lock()

        def synthetic_image_proxy():
            raw = request.args.get('url', '')
            index = image_fixture_index(raw)
            if index is None or not request.args.get('h'):
                abort(404)
            with proxy_lock:
                proxy_seen[index] += 1
            return Response(synthetic_image_png(index), mimetype='image/png', headers={
                'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            })

        image_measurements = []
        image_report = {'scope': 'synthetic-loopback-only',
                        'owner_mockup_fidelity_accepted': False,
                        'measurements': image_measurements}
        with (patch('searx.search.SearchWithPlugins', SyntheticBrowserImageResultsCollection),
              patch.dict(app.view_functions, {'image_proxy': synthetic_image_proxy})):
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
                    lambda page: len(page.find_elements(By.CSS_SELECTOR, '#urls.goreecloud-image-results article.result-images')) == IMAGE_GALLERY_COUNT
                )
                geometry = driver.execute_script("""
                    const root=document.querySelector('#urls');
                    const cards=[...root.querySelectorAll('article.result-images')];
                    const image=cards[0].querySelector('img.image_thumbnail');
                    const loadAll=root.querySelector('#goreecloud-image-load-all');
                    const css=getComputedStyle(root);
                    const cr=cards.map(c=>c.getBoundingClientRect());
                    const widths=new Set(cr.map(r=>Math.round(r.left)));
                    return {display:css.display, columns:css.gridTemplateColumns.split(' ').length,
                        gcConsumer:document.documentElement.getAttribute('data-gc-consumer'),
                        imageLoadTarget:loadAll?.getBoundingClientRect().height ?? 0,
                        imageLoadButton:loadAll?.type === 'button' && !loadAll.disabled,
                        targetToken:getComputedStyle(document.documentElement).getPropertyValue('--gc-v1-component-button-height-medium').trim(),
                        distinctX:widths.size, viewport:document.documentElement.clientWidth,
                        scroll:document.documentElement.scrollWidth,
                        cardWidth:cr[0].width, imageWidth:image.getBoundingClientRect().width,
                        proxiedImages:cards.every(c=>{
                            const image=c.querySelector('img.image_thumbnail');
                            const src=new URL(image.currentSrc || image.src, location.href);
                            return src.origin===location.origin && src.pathname==='/image_proxy';
                        }),
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
                assert geometry['gcConsumer'] == 'goreecloud-search', (label, geometry)
                assert geometry['imageLoadButton'] and geometry['imageLoadTarget'] >= 44, (label, geometry)
                assert geometry['targetToken'] == '44px', (label, geometry)
                assert geometry['proxiedImages'], (label, geometry)
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
                # Real pointer activation must request any remaining lazy
                # thumbnails. It is valid for Chrome to have already loaded
                # some or all thumbnails while filling the first viewport.
                load_all = driver.find_element(By.ID, 'goreecloud-image-load-all')
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center',behavior:'instant'})", load_all
                )
                load_all.click()
                WebDriverWait(driver, 12).until(
                    lambda page: page.find_element(By.ID, 'goreecloud-image-load-all').get_attribute('disabled')
                    and page.find_element(By.ID, 'goreecloud-image-load-all').text == 'Previews requested'
                )
                WebDriverWait(driver, 12).until(
                    lambda page: page.execute_script("""
                        const imgs=[...document.querySelectorAll('#urls article.result-images img.image_thumbnail')];
                        return imgs.length === arguments[0] && imgs.every(img => img.complete);
                    """, IMAGE_GALLERY_COUNT)
                )
                # naturalWidth alone is metadata, not proof that Chrome can
                # decode an image. Real decode() must resolve on every image.
                decoded = driver.execute_async_script("""
                    const done=arguments[arguments.length-1];
                    const imgs=[...document.querySelectorAll('#urls article.result-images img.image_thumbnail')];
                    Promise.all(imgs.map(img => img.decode().then(() => true, () => false)))
                        .then(done, () => done([]));
                """)
                rendering = driver.execute_script("""
                    const imgs=[...document.querySelectorAll('#urls article.result-images img.image_thumbnail')];
                    const cards=[...document.querySelectorAll('#urls article.result-images')];
                    const root=document.documentElement;
                    const rects=cards.map(card => card.getBoundingClientRect());
                    const imageRects=imgs.map(img => img.getBoundingClientRect());
                    const seenColumns=new Set(rects.map(rect => Math.round(rect.left)));
                    const externalImages=performance.getEntriesByType('resource').filter(entry => {
                        if (entry.initiatorType !== 'img') return false;
                        try { return new URL(entry.name).origin !== location.origin; }
                        catch { return true; }
                    });
                    const status=document.getElementById('goreecloud-image-load-status');
                    return {
                        viewport_width:root.clientWidth,
                        viewport_height:innerHeight,
                        page_scroll_width:root.scrollWidth,
                        card_count:cards.length,
                        image_count:imgs.length,
                        loaded_count:imgs.filter(img => img.complete && img.naturalWidth===4 && img.naturalHeight===3).length,
                        unavailable_count:cards.filter(card => card.classList.contains('goreecloud-thumbnail-unavailable')).length,
                        // On a 320px device two 4:3 image columns have ~126px
                        // previews with ~95px heights. Check responsive
                        // dimensions/aspect ratio, not a desktop height floor.
                        visible_image_count:imageRects.filter(rect => rect.width>=100 &&
                            rect.height>=70 && rect.height/rect.width>=0.70 &&
                            rect.height/rect.width<=0.85).length,
                        grid_columns:seenColumns.size,
                        minimum_card_width:Math.round(Math.min(...rects.map(rect => rect.width))),
                        minimum_image_width:Math.round(Math.min(...imageRects.map(rect => rect.width))),
                        minimum_image_height:Math.round(Math.min(...imageRects.map(rect => rect.height))),
                        external_image_requests:externalImages.length,
                        previews_action_finished:!!status && /of \\d+ additional previews checked \\(\\d+ loaded, \\d+ unavailable\\)\\./.test(status.textContent),
                        previews_action_disabled:document.getElementById('goreecloud-image-load-all').disabled
                    };
                """)
                with proxy_lock:
                    unique_proxy_fixtures = len(proxy_seen)
                image_measurements.append({'viewport': label, **rendering,
                                           'decoded_count': sum(bool(ok) for ok in decoded),
                                           'unique_local_proxy_fixtures': unique_proxy_fixtures})
                # Preserve observations and screenshot even if a subsequent
                # acceptance assertion fails, to make CI failures actionable.
                (artifacts / 'image-acceptance-layout.json').write_text(
                    json.dumps(image_report, indent=2, sort_keys=True) + '\n', encoding='utf-8'
                )
                driver.execute_script('window.scrollTo(0, 0)')
                driver.save_screenshot(str(artifacts / f'{label}-image-gallery.png'))
                assert len(decoded) == IMAGE_GALLERY_COUNT and all(decoded), (label, 'PNG decode failed')
                assert rendering['image_count'] == IMAGE_GALLERY_COUNT, (label, rendering)
                assert rendering['loaded_count'] == IMAGE_GALLERY_COUNT, (label, rendering)
                assert rendering['unavailable_count'] == 0, (label, rendering)
                assert rendering['visible_image_count'] == IMAGE_GALLERY_COUNT, (label, rendering)
                assert rendering['external_image_requests'] == 0, (label, rendering)
                assert rendering['previews_action_finished'] and rendering['previews_action_disabled'], (label, rendering)
                assert rendering['page_scroll_width'] <= rendering['viewport_width'] + 1, (label, rendering)
                assert rendering['minimum_card_width'] >= 120 and rendering['minimum_image_width'] >= 100, (label, rendering)
                assert rendering['minimum_image_height'] >= 70, (label, rendering)
                if label == 'desktop':
                    assert rendering['grid_columns'] >= 4, (label, rendering)
                else:
                    assert rendering['grid_columns'] == 2, (label, rendering)
                assert unique_proxy_fixtures == IMAGE_GALLERY_COUNT, (label, unique_proxy_fixtures)
                first = driver.find_element(By.CSS_SELECTOR, '#urls article.result-images')
                first.find_element(By.CSS_SELECTOR, 'a').click()
                WebDriverWait(driver, 5).until(
                    lambda page: 'image-detail-open' in page.find_element(By.ID, 'results').get_attribute('class')
                )
                assert driver.current_url.endswith('#image-viewer'), 'Image viewer should open in page'
                assert not driver.execute_script('return location.search'), 'Image viewer leaked search query'
                WebDriverWait(driver, 5).until(lambda page: page.execute_script("""
                    const img=document.querySelector('.result-images[data-vim-selected] .result-images-source img');
                    return !!img && img.complete && img.naturalWidth===4 && img.naturalHeight===3;
                """))
                driver.find_element(By.CSS_SELECTOR,
                                    '.result-images[data-vim-selected] .result-detail-next').click()
                WebDriverWait(driver, 5).until(lambda page: page.execute_script("""
                    const cards=[...document.querySelectorAll('#urls article.result-images')];
                    return cards[1]?.hasAttribute('data-vim-selected')===true;
                """))
                driver.find_element(By.CSS_SELECTOR, '.result-images[data-vim-selected] .result-detail-close').click()
                WebDriverWait(driver, 5).until(
                    lambda page: 'image-detail-open' not in page.find_element(By.ID, 'results').get_attribute('class')
                )
        # Only aggregate fixture counts/layout numbers are exported; neither
        # user queries nor source/proxy URLs belong in CI screenshots/reports.
        print('IMAGE ACCEPTANCE', json.dumps(image_report, sort_keys=True), flush=True)
        step_summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if step_summary:
            lines = [
                '### GoreeCloud Search — synthetic Chrome Images gate',
                '',
                '| Viewport | Decoded PNGs | Grid columns | Horizontal overflow | External image requests |',
                '| --- | ---: | ---: | ---: | ---: |',
            ]
            for item in image_measurements:
                lines.append(
                    f"| {item['viewport']} | {item['decoded_count']}/{IMAGE_GALLERY_COUNT} | "
                    f"{item['grid_columns']} | "
                    f"{item['page_scroll_width'] - item['viewport_width']}px | "
                    f"{item['external_image_requests']} |"
                )
            lines += ['', 'Screenshots and numeric measurements are retained as short-lived CI artifacts.',
                      'Owner mockup visual fidelity remains unaccepted; synthetic runtime checks only.', '']
            with Path(step_summary).open('a', encoding='utf-8') as summary:
                summary.write('\n'.join(lines) + '\n')
        print(f'PASS desktop and phone image grid, all {IMAGE_GALLERY_COUNT} decoded local proxy PNGs per viewport, image details and POST privacy')

        # A provider error must not force the desktop retry/source panel into
        # a second off-screen grid column on phones or tablets. Verify actual
        # browser geometry, not only the presence of media-query CSS text.
        empty_image_measurements = []
        with patch('searx.search.SearchWithPlugins', SyntheticBrowserFailedImageSearch):
            for width, height, label in ((1440, 900, 'desktop'), (768, 900, 'tablet'),
                                         (390, 844, 'phone'), (320, 760, 'phone-small')):
                driver.set_window_size(width, height)
                driver.get(url)
                driver.find_element(By.ID, 'q').send_keys('synthetic image outage')
                driver.find_element(By.ID, 'send_search').click()
                WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                    lambda page: page.current_url.endswith('/search') and
                    bool(page.find_elements(By.CSS_SELECTOR, '.goreecloud-category-form'))
                )
                driver.find_element(By.XPATH,
                    "//nav[contains(@class,'goreecloud-category-tabs')]//button[normalize-space()='Images']").click()
                WebDriverWait(driver, 12, ignored_exceptions=(StaleElementReferenceException,)).until(
                    lambda page: bool(page.find_elements(By.CSS_SELECTOR,
                        '#urls.goreecloud-image-results .goreecloud-empty-state'))
                )
                geometry = driver.execute_script("""
                    const root=document.documentElement;
                    const results=document.querySelector('#main_results #results');
                    const empty=document.querySelector('#urls.goreecloud-image-results .goreecloud-empty-state');
                    const sidebar=document.querySelector('#results > #sidebar');
                    const panel=sidebar?.querySelector('.goreecloud-source-diagnostics');
                    const r=e=>e.getBoundingClientRect();
                    const a=r(empty), b=r(sidebar);
                    return {
                        viewport:root.clientWidth, scroll:root.scrollWidth,
                        grid_columns:getComputedStyle(results).gridTemplateColumns.split(' ').length,
                        empty_width:Math.round(a.width), sidebar_width:Math.round(b.width),
                        sidebar_visible:b.width>0 && b.height>0,
                        sidebar_within_viewport:b.left>=-1 && b.right<=root.clientWidth+1,
                        sidebar_below:b.top>=a.bottom-1,
                        sidebar_beside:b.left>=a.right-1,
                        details_present:!!panel, retry_method:empty.querySelector('form.goreecloud-empty-retry')?.method,
                        external_image_requests:performance.getEntriesByType('resource').filter(e=>
                            e.initiatorType==='img' && new URL(e.name, location.href).origin!==location.origin).length
                    };
                """)
                empty_image_measurements.append({'viewport_name': label, **geometry})
                driver.save_screenshot(str(artifacts / f'{label}-image-empty-outage.png'))
                assert geometry['scroll']<=geometry['viewport']+1, (label, geometry)
                assert geometry['sidebar_visible'] and geometry['sidebar_within_viewport'], (label, geometry)
                assert geometry['details_present'] and geometry['retry_method']=='post', (label, geometry)
                assert geometry['external_image_requests']==0, (label, geometry)
                if label=='desktop':
                    assert geometry['grid_columns']==2 and geometry['sidebar_beside'], (label, geometry)
                else:
                    assert geometry['grid_columns']==1 and geometry['sidebar_below'], (label, geometry)
        (artifacts / 'image-empty-layout.json').write_text(
            json.dumps({'scope':'offline-synthetic-only', 'owner_mockup_accepted':False,
                        'measurements':empty_image_measurements}, indent=2, sort_keys=True) + '\n',
            encoding='utf-8')
        print('IMAGE EMPTY LAYOUT', json.dumps(empty_image_measurements, sort_keys=True), flush=True)
        print('PASS responsive Images outage: truthful retry/sidebar, no overflow or external images')

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
            # Verify the actual computed GC UI category touch geometry and
            # native POST forms before following a category transition.
            category_contract = driver.execute_script("""
                const root=document.documentElement;
                const nav=document.querySelector('nav.goreecloud-category-tabs');
                const buttons=[...nav.querySelectorAll('form button.goreecloud-category-tab')];
                const current=buttons.filter(b=>b.getAttribute('aria-current')==='page');
                const tokens=getComputedStyle(root);
                return {
                    gcConsumer:root.dataset.gcConsumer,
                    comfortableTarget:tokens.getPropertyValue('--gc-v1-foundation-target-comfortable').trim(),
                    categoryTargetHeights:buttons.map(b=>b.getBoundingClientRect().height),
                    postOnly:[...nav.querySelectorAll('form')].every(f=>f.method==='post' &&
                        f.action.endsWith('/search') && !f.action.includes('?')),
                    currentCount:current.length,
                    disabled:[...nav.querySelectorAll('[aria-disabled="true"]')].length
                };
            """)
            assert category_contract['gcConsumer'] == 'goreecloud-search', category_contract
            assert category_contract['comfortableTarget'] == '44px', category_contract
            assert min(category_contract['categoryTargetHeights']) >= 44, category_contract
            assert category_contract['postOnly'], category_contract
            assert category_contract['currentCount'] == 1, category_contract
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
            mobile_heights = driver.execute_script("""
                return [...document.querySelectorAll('.goreecloud-category-tab')]
                    .map(tab=>tab.getBoundingClientRect().height)
            """)
            assert min(mobile_heights) >= 44, mobile_heights
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
            summary = driver.find_element(By.CSS_SELECTOR, '.goreecloud-source-diagnostics > summary')
            summary.send_keys(Keys.SPACE)
            summary_focus = driver.execute_script("""
              const summary=arguments[0];
              const style=getComputedStyle(summary);
              return {expanded:summary.parentElement.open,
                focused:document.activeElement===summary,
                visible:summary.matches(':focus-visible'),
                outline:style.outlineStyle, outlineWidth:parseFloat(style.outlineWidth)};
            """, summary)
            assert summary_focus['expanded'] and summary_focus['focused'] and summary_focus['visible'], summary_focus
            assert summary_focus['outline'] == 'solid' and summary_focus['outlineWidth'] >= 3, summary_focus
            retry = driver.find_element(By.CSS_SELECTOR, '.goreecloud-partial-retry button')
            assert retry.is_displayed(), 'Partial retry action hidden'
            for width, height, label in ((1440, 900, 'desktop'), (390, 844, 'phone'), (320, 760, 'phone-small')):
                driver.set_window_size(width, height)
                controls = driver.execute_script("""
                  const root=document.documentElement;
                  const details=document.querySelector('.goreecloud-source-diagnostics');
                  const summary=details.querySelector('summary');
                  const retry=details.querySelector('.goreecloud-partial-retry button');
                  return {consumer:root.getAttribute('data-gc-consumer'),
                    targetToken:getComputedStyle(root).getPropertyValue('--gc-v1-foundation-target-comfortable').trim(),
                    buttonToken:getComputedStyle(root).getPropertyValue('--gc-v1-component-button-height-medium').trim(),
                    open:details.open,
                    summaryHeight:summary.getBoundingClientRect().height,
                    summaryMarker:getComputedStyle(summary).display,
                    buttonHeight:retry.getBoundingClientRect().height,
                    nativePost:retry.type==='submit' && retry.form?.method==='post',
                    viewport:root.clientWidth, scroll:root.scrollWidth};
                """)
                assert controls['consumer'] == 'goreecloud-search', (label, controls)
                assert controls['open'] and controls['summaryMarker'] == 'list-item', (label, controls)
                assert controls['targetToken'] == '44px' and controls['summaryHeight'] >= 44, (label, controls)
                assert controls['buttonToken'] == '44px' and controls['buttonHeight'] >= 44, (label, controls)
                assert controls['nativePost'], (label, controls)
                assert controls['scroll'] <= controls['viewport'] + 1, (label, controls)
            driver.set_window_size(1440, 900)
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
