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
from selenium.common.exceptions import WebDriverException  # noqa: E402
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


def set_css_viewport(driver, width: int, height: int) -> None:
    """Force real CSS pixels: headless Chrome may clamp outer windows below 500px."""
    driver.set_window_size(width, height)
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
    })
    actual = driver.execute_script("return {width:innerWidth, height:innerHeight}")
    assert actual == {"width": width, "height": height}, (width, height, actual)


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


def pointer_geometry(driver, selector: str) -> dict:
    """Diagnose scroll containers and the actual browser hit target, without query data."""
    return driver.execute_script("""
      const target = document.querySelector(arguments[0]);
      const rect = target.getBoundingClientRect();
      const centerX = (rect.left + rect.right) / 2;
      const centerY = (rect.top + rect.bottom) / 2;
      const hit = document.elementFromPoint(centerX, centerY);
      const scroller = document.scrollingElement;
      const ancestors = [];
      for (let node = target; node && ancestors.length < 7; node = node.parentElement) {
        const style = getComputedStyle(node);
        ancestors.push({tag:node.tagName, id:node.id, position:style.position,
          overflowY:style.overflowY, height:style.height,
          scrollTop:node.scrollTop, scrollHeight:node.scrollHeight,
          clientHeight:node.clientHeight});
      }
      return {
        innerWidth:window.innerWidth, innerHeight:window.innerHeight,
        scrollY:window.scrollY, scrollingElement:scroller?.tagName,
        scrollTop:scroller?.scrollTop, scrollHeight:scroller?.scrollHeight,
        clientHeight:scroller?.clientHeight,
        htmlOverflow:getComputedStyle(document.documentElement).overflowY,
        htmlScrollBehavior:getComputedStyle(document.documentElement).scrollBehavior,
        htmlHeight:getComputedStyle(document.documentElement).height,
        bodyOverflow:getComputedStyle(document.body).overflowY,
        bodyHeight:getComputedStyle(document.body).height,
        ancestors,
        targetTop:rect.top, targetBottom:rect.bottom,
        targetHeight:rect.height, centerX, centerY,
        hitTag:hit?.tagName, hitId:hit?.id,
        hitClass:typeof hit?.className === 'string' ? hit.className : '',
        hitWithinTarget:hit === target || target.contains(hit),
      };
    """, selector)


def assert_pointer_hit(driver, selector: str, label: str) -> dict:
    geometry = pointer_geometry(driver, selector)
    assert geometry["scrollHeight"] > geometry["clientHeight"] + 5, (label, geometry)
    assert geometry["htmlScrollBehavior"] == "auto", (label, geometry)
    visible = (0 <= geometry["centerX"] < geometry["innerWidth"] and
               0 <= geometry["centerY"] < geometry["innerHeight"] and
               geometry["hitWithinTarget"])
    if not visible:
        # Diagnostic only: do not turn a failed click into a JS-activated pass.
        # Test whether root scrolling can move at all, then fail with both probes.
        scroll_to_probe = driver.execute_script("""
          const root = document.scrollingElement;
          const before = {scrollY:scrollY, scrollTop:root.scrollTop};
          const reachable = Math.max(0, root.scrollHeight - root.clientHeight);
          window.scrollTo({top:Math.min(reachable,root.scrollTop + 240),behavior:'instant'});
          return {before, after:{scrollY:scrollY,scrollTop:root.scrollTop},reachable};
        """)
        raise AssertionError((label, geometry, {"scrollToProbe": scroll_to_probe}))
    return geometry


def click_native_pointer(driver, selector: str, label: str, *, navigates: bool = False) -> None:
    """Scroll to an actual hit target, then click with WebDriver's native pointer."""
    target = driver.find_element(By.CSS_SELECTOR, selector)
    before = pointer_geometry(driver, selector)
    # Chrome's implicit WebDriver scrolling can stop almost immediately when
    # the document root has an auto-height scrollport. Verify usable scrolling
    # and actual hit-testing before sending any pointer activation.
    driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'nearest'})", target)
    scrolled = assert_pointer_hit(driver, selector, label)
    if before["targetTop"] >= before["innerHeight"]:
        assert scrolled["scrollTop"] > before["scrollTop"], (label, before, scrolled)
    try:
        target.click()
    except WebDriverException as error:
        after = pointer_geometry(driver, selector)
        raise AssertionError(f"{label}: real pointer click failed: {before}; {after}") from error
    if navigates:
        # An actual POST replaces the document; the caller checks its results.
        return
    assert_pointer_hit(driver, selector, label)


def tap_native_touch(driver, selector: str, label: str) -> None:
    """Inject a trusted Chromium touch pointer at the hit-tested visible target."""
    target = driver.find_element(By.CSS_SELECTOR, selector)
    driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'nearest'})", target)
    geometry = assert_pointer_hit(driver, selector, label)
    point = {"x": round(geometry["centerX"]), "y": round(geometry["centerY"]), "id": 1}
    driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1})
    try:
        driver.execute_cdp_cmd("Input.dispatchTouchEvent", {
            "type": "touchStart", "touchPoints": [point],
        })
        driver.execute_cdp_cmd("Input.dispatchTouchEvent", {
            "type": "touchEnd", "touchPoints": [],
        })
    finally:
        driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": False})


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
                set_css_viewport(driver, width, height)
                post_synthetic_preview(driver, url)
                # Details must be reachable by real pointer input below the initial fold.
                assert driver.find_element(By.CSS_SELECTOR, "details.goreecloud-preview-single").get_attribute("open") is None
                if label == "small-phone":
                    tap_native_touch(driver, ".goreecloud-preview-single summary", label)
                else:
                    click_native_pointer(driver, ".goreecloud-preview-single summary", label)
                assert driver.find_element(By.CSS_SELECTOR, "details.goreecloud-preview-single").get_attribute("open") is not None
                assert_preview_geometry(driver, label)
            set_css_viewport(driver, 1440, 900)
            post_synthetic_preview(driver, url)
            assert_keyboard_and_tokens(driver)
            assert_forced_colors(driver)
            network.assert_not_called()
            print("PASS private preflight no-egress, GC UI tokens, 320/390/1440 pointer/touch, keyboard, forced colors")

        # Actual provider-choice submission, still without a provider call.
        with patch("searx.search.SearchWithPlugins", SyntheticSearch):
            for width, height, label in ((1440, 900, "desktop"), (320, 760, "small-phone")):
                set_css_viewport(driver, width, height)
                post_synthetic_preview(driver, url)
                if label == "small-phone":
                    tap_native_touch(driver, ".goreecloud-preview-single summary", label)
                else:
                    click_native_pointer(driver, ".goreecloud-preview-single summary", label)
                assert driver.find_element(By.CSS_SELECTOR, "details.goreecloud-preview-single").get_attribute("open") is not None
                selected = driver.find_element(By.ID, "goreecloud-provider-choice")
                first_provider = selected.find_elements(By.CSS_SELECTOR, 'option[value]:not([value=""])')[0]
                Select(selected).select_by_value(first_provider.get_attribute("value"))
                if label == "small-phone":
                    tap_native_touch(driver, ".goreecloud-preview-single button[type=submit]", label)
                else:
                    click_native_pointer(driver, ".goreecloud-preview-single button[type=submit]", label, navigates=True)
                WebDriverWait(driver, 12).until(lambda browser: browser.current_url.endswith("/search"))
                assert "?" not in driver.current_url
                assert driver.find_elements(By.CSS_SELECTOR, ".goreecloud-source-diagnostics")
        print("PASS real pointer/touch native single-provider POST at 320/1440; no query URL")
    finally:
        if driver is not None:
            driver.quit()
        server.shutdown()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
