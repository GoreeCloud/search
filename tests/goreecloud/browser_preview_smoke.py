"""No-provider Chrome smoke for Search's opt-in GC UI private preview.

The fixture opens /preview through a real browser POST and uses only a
synthetic search result if the single-source Continue button is submitted.
No screenshots, external providers, request bodies or real queries are saved.
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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/goreecloud"))
os.environ["SEARXNG_SETTINGS_PATH"] = str(ROOT / "configs/goreecloud/settings.yml")
os.environ["SEARXNG_SECRET"] = secrets.token_hex(32)

from gc_ui_preview_offline import offline_preview_app  # noqa: E402
from selenium import webdriver  # noqa: E402
from selenium.webdriver.chrome.options import Options  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.common.keys import Keys  # noqa: E402
from selenium.webdriver.support.ui import Select, WebDriverWait  # noqa: E402


class SyntheticSearch:
    """Isolated parser and results-page path, without any provider dispatch."""

    def __init__(self, search_query, *args):
        self.search_query = search_query

    def search(self):
        return SimpleNamespace(
            redirect_url=None, suggestions=[], corrections=[], answers=[],
            infoboxes=[], engine_data={}, paging=False, unresponsive_engines=[],
            get_timings=lambda: [], get_ordered_results=lambda: [],
        )


def post_synthetic_preview(driver, url: str) -> None:
    """Browser-native POST, not GET; browser history never receives the query."""
    driver.get(url)
    driver.execute_script("""
      const form = document.createElement('form');
      form.method = 'post'; form.action = '/preview';
      for (const [name, value] of Object.entries({
        q:'synthetic preview browser acceptance',
        category_general:'1', language:'en', safesearch:'2'
      })) {
        const input = document.createElement('input');
        input.type = 'hidden'; input.name = name; input.value = value;
        form.append(input);
      }
      document.body.append(form);
      form.submit();
    """)
    WebDriverWait(driver, 12).until(
        lambda browser: browser.current_url.endswith("/preview") and
        bool(browser.find_elements(By.CSS_SELECTOR, ".goreecloud-preview h1"))
    )
    assert "?" not in driver.current_url


def assert_preview_geometry(driver, label: str) -> None:
    geometry = driver.execute_script("""
      const panel = document.querySelector('.goreecloud-preview');
      const summary = panel.querySelector('.goreecloud-preview-single summary');
      const select = panel.querySelector('select[name=engines]');
      const buttons = [...panel.querySelectorAll('.goreecloud-preview-continue')];
      const rect = element => element.getBoundingClientRect();
      const root = document.documentElement;
      return {
        consumer:root.getAttribute('data-gc-consumer'),
        panel: {left:rect(panel).left, right:rect(panel).right, width:rect(panel).width},
        viewport:root.clientWidth, overflow:root.scrollWidth-root.clientWidth,
        summaryHeight:rect(summary).height, selectHeight:rect(select).height,
        buttonHeights:buttons.map(button => rect(button).height),
        labelConnected:panel.querySelector('label[for="goreecloud-provider-choice"]')?.control === select,
        buttonToken:getComputedStyle(root).getPropertyValue('--gc-v1-component-button-height-medium').trim(),
        formMethods:[...panel.querySelectorAll('form')].map(form => form.method),
        formActions:[...panel.querySelectorAll('form')].map(form => new URL(form.action).pathname),
      };
    """)
    assert geometry["consumer"] == "goreecloud-search", (label, geometry)
    assert geometry["buttonToken"] == "44px", (label, geometry)
    assert geometry["labelConnected"], (label, geometry)
    assert geometry["formMethods"] == ["post", "post"], (label, geometry)
    assert geometry["formActions"] == ["/search", "/search"], (label, geometry)
    assert geometry["panel"]["left"] >= -1, (label, geometry)
    assert geometry["panel"]["right"] <= geometry["viewport"] + 1, (label, geometry)
    assert geometry["summaryHeight"] >= 44, (label, geometry)
    assert geometry["selectHeight"] >= 44, (label, geometry)
    assert len(geometry["buttonHeights"]) == 2, (label, geometry)
    assert all(height >= 44 for height in geometry["buttonHeights"]), (label, geometry)
    assert geometry["overflow"] <= 2, (label, geometry)


def assert_keyboard_and_tokens(driver) -> None:
    panel = driver.find_element(By.CLASS_NAME, "goreecloud-preview")
    summary = panel.find_element(By.CSS_SELECTOR, ".goreecloud-preview-single summary")
    details = panel.find_element(By.CSS_SELECTOR, "details.goreecloud-preview-single")
    assert details.get_attribute("open") is None, "Single-source details must start closed"
    summary.send_keys(Keys.ENTER)
    assert details.get_attribute("open") is not None, "Enter should open native details"
    summary.send_keys(Keys.TAB)
    focus = driver.execute_script("""
      const select = document.querySelector('#goreecloud-provider-choice');
      const style = getComputedStyle(select);
      return {active:document.activeElement === select,
              outlineStyle:style.outlineStyle,
              outlineWidth:parseFloat(style.outlineWidth),
              outlineColor:style.outlineColor};
    """)
    assert focus["active"] and focus["outlineStyle"] == "solid", focus
    assert focus["outlineWidth"] >= 3, focus

    for mode in ("light", "dark"):
        colors = driver.execute_script("""
          document.documentElement.setAttribute('data-gc-mode', arguments[0]);
          const panel = document.querySelector('.goreecloud-preview');
          const button = panel.querySelector('.goreecloud-preview-continue');
          const probe = document.createElement('span');
          probe.style.background = 'var(--gc-v1-color-primary)';
          probe.style.color = 'var(--gc-v1-color-on-primary)';
          document.body.append(probe);
          const actual = getComputedStyle(button), expected = getComputedStyle(probe);
          const result = {background:actual.backgroundColor, expected:expected.backgroundColor,
                          color:actual.color, expectedText:expected.color,
                          focusToken:getComputedStyle(document.documentElement)
                            .getPropertyValue('--gc-v1-color-focus-ring').trim()};
          probe.remove();
          return result;
        """, mode)
        assert colors["background"] == colors["expected"], (mode, colors)
        assert colors["color"] == colors["expectedText"], (mode, colors)
        assert colors["focusToken"], (mode, colors)


def assert_forced_colors(driver) -> None:
    driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {
        "features": [{"name": "forced-colors", "value": "active"}],
    })
    try:
        visual = driver.execute_script("""
          const panel = document.querySelector('.goreecloud-preview');
          const button = panel.querySelector('.goreecloud-preview-continue');
          const select = panel.querySelector('select');
          const probe = document.createElement('span');
          probe.style.cssText='background:ButtonFace;color:ButtonText;outline:3px solid Highlight';
          document.body.append(probe);
          const expected=getComputedStyle(probe);
          const result={active:matchMedia('(forced-colors: active)').matches,
            shadow:getComputedStyle(panel).boxShadow,
            background:getComputedStyle(button).backgroundColor,
            expectedBackground:expected.backgroundColor,
            foreground:getComputedStyle(button).color,
            expectedForeground:expected.color,
            selectBorder:getComputedStyle(select).borderStyle};
          probe.remove(); return result;
        """)
        assert visual["active"], visual
        assert visual["shadow"] == "none", visual
        assert visual["background"] == visual["expectedBackground"], visual
        assert visual["foreground"] == visual["expectedForeground"], visual
        assert visual["selectBorder"] == "solid", visual
    finally:
        driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"features": []})


def main() -> None:
    server = make_server("127.0.0.1", 0, offline_preview_app(), threaded=True)
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
        with patch("searx.search.SearchWithPlugins") as network:
            for width, height, label in (
                (1440, 900, "desktop"), (390, 844, "phone"), (320, 760, "small-phone"),
            ):
                driver.set_window_size(width, height)
                post_synthetic_preview(driver, url)
                # Native details are deliberately closed before the first keyboard interaction.
                driver.find_element(By.CSS_SELECTOR, ".goreecloud-preview-single summary").send_keys(Keys.ENTER)
                assert_preview_geometry(driver, label)
            post_synthetic_preview(driver, url)
            assert_keyboard_and_tokens(driver)
            assert_forced_colors(driver)
            network.assert_not_called()
            print("PASS private preflight no-egress, GC UI tokens, 320/390/1440 geometry, keyboard, forced colors")

        # Actual provider-choice submission, still without a provider call.
        with patch("searx.search.SearchWithPlugins", SyntheticSearch):
            # Submit from a fresh desktop page: the responsive-width assertions
            # above intentionally leave Chrome at 320px with a long page scroll.
            driver.set_window_size(1440, 900)
            post_synthetic_preview(driver, url)
            driver.find_element(By.CSS_SELECTOR, ".goreecloud-preview-single summary").click()
            selected = driver.find_element(By.ID, "goreecloud-provider-choice")
            first_provider = selected.find_elements(By.CSS_SELECTOR, 'option[value]:not([value=""])')[0]
            Select(selected).select_by_value(first_provider.get_attribute("value"))
            submit = driver.find_element(By.CSS_SELECTOR, ".goreecloud-preview-single button[type=submit]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", submit)
            submit.click()
            WebDriverWait(driver, 12).until(lambda browser: browser.current_url.endswith("/search"))
            assert "?" not in driver.current_url
            assert driver.find_elements(By.CSS_SELECTOR, ".goreecloud-source-diagnostics")
        print("PASS native single-provider POST to isolated synthetic Search results; no query URL")
    finally:
        if driver is not None:
            driver.quit()
        server.shutdown()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
