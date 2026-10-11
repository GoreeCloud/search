"""Browser-only, no-provider home UI smoke. Requires Selenium and Chrome.

Runs against an ephemeral loopback Flask WSGI server. No search is dispatched and
screenshots contain only the unauthenticated synthetic homepage.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import sys
from threading import Thread

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # direct-script CI launch from nested tests directory
os.environ["SEARXNG_SETTINGS_PATH"] = str(ROOT / "configs/goreecloud/settings.yml")
os.environ["SEARXNG_SECRET"] = secrets.token_hex(32)

from searx.webapp import app  # noqa: E402

from selenium import webdriver  # noqa: E402
from selenium.webdriver.chrome.options import Options  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402


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
