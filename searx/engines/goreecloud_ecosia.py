# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ecosia Web adapter for the private GoreeCloud Search federation.

Ecosia exposes no documented public metasearch API. This explicitly bounded
HTML adapter can return empty results when the upstream markup changes; it
never pretends Bing/Google results were retrieved from Ecosia.
"""
from __future__ import annotations

from urllib.parse import urlencode, urlsplit

from searx.exceptions import SearxEngineAccessDeniedException
from searx.goreecloud_policy import safe_primary_result_url
from searx.result_types import EngineResults
from searx.utils import extract_text

about = {
    "website": "https://www.ecosia.org",
    "official_api_documentation": None,
    "use_official_api": False,
    "require_api_key": False,
    "results": "HTML",
}
categories = ["general"]
paging = False
base_url = "https://www.ecosia.org"


def request(query, params):
    """Use SearXNG's configured proxied provider transport."""
    params["url"] = base_url + "/search?" + urlencode({"q": query})
    return params


def response(resp):
    """Only publish explicit external HTTPS links from recognizable result cards."""
    page = resp.html()
    if page.xpath(
        '//input[@name="cf-turnstile-response"]'
        ' | //*[contains(translate(@id,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"captcha") '
        'or contains(translate(@class,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"captcha")]'
    ):
        raise SearxEngineAccessDeniedException(message="Ecosia challenged the private search relay")
    results = EngineResults()
    seen = set()
    cards = page.xpath(
        '//*[@data-test-id="mainline-result-web" or @data-test-id="result" or @data-testid="result"]'
        ' | //article[contains(concat(" ", normalize-space(@class), " "), " result ")]'
        ' | //div[contains(concat(" ", normalize-space(@class), " "), " result ")]'
    )
    for card in cards:
        links = card.xpath(
            './/a[@data-test-id="result-link"][@href]'
            ' | .//h2//a[@href] | .//h3//a[@href]'
            ' | .//a[contains(@class,"result__link")][@href]'
            ' | .//a[contains(@class,"result-title")][@href]'
        )
        if not links:
            continue
        link = links[0]
        target = link.get("href", "")
        titles = card.xpath('.//*[@data-test-id="result-title"]')
        title = (extract_text(titles[0]) if titles else extract_text(link)).strip()
        if not title or not safe_primary_result_url(target):
            continue
        # Direct outgoing result links only; never expose Ecosia click trackers.
        parsed = urlsplit(target)
        if parsed.scheme.lower() != "https" or parsed.hostname in ("ecosia.org", "www.ecosia.org"):
            continue
        if target in seen:
            continue
        seen.add(target)
        descriptions = card.xpath(
            './/*[contains(@class,"description") or contains(@class,"snippet") '
            'or @data-test-id="snippet" or @data-test-id="result-description"]'
        )
        content = extract_text(descriptions[0]).strip() if descriptions else ""
        results.add(results.types.MainResult(url=target, title=title, content=content))
    return results
