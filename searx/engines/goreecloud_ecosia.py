# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ecosia Web adapter for the private GoreeCloud Search federation.

Ecosia exposes no documented public metasearch API. This explicitly bounded
HTML adapter can return empty results when the upstream markup changes; it
never pretends Bing/Google results were retrieved from Ecosia.
"""
from __future__ import annotations

from urllib.parse import urlencode, urlsplit

from searx.exceptions import SearxEngineAccessDeniedException, SearxEngineAPIException
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
    # Restrict candidate cards to organic web hits. Avoid ad and navigation
    # cards: a linked title by itself does not establish an organic result.
    cards = page.xpath(
        '//*[@data-test-id="mainline-result-web" or @data-test-id="organic-result"'
        ' or @data-test-id="result" or @data-testid="result"]'
    )
    if not cards and not page.xpath(
        '//*[@data-test-id="web-no-results" or @data-testid="web-no-results"]'
    ):
        # A redesign or an unrecognized challenge is an upstream failure, not
        # a valid zero-result search. Never claim a source returned no matches.
        raise SearxEngineAPIException("Ecosia web result markup unavailable")
    for card in cards:
        # Some variants wrap their result title inside the link; others use
        # an explicit result-link attribute. Prefer those over sitelinks.
        link = None
        for selector in (
            './/a[@data-test-id="result-link"][@href]',
            './/*[@data-test-id="result-title"]/ancestor::a[@href][1]',
            './/h2//a[@href] | .//h3//a[@href]',
            './/a[contains(@class,"result__link")][@href]',
            './/a[contains(@class,"result-title")][@href]',
        ):
            links = card.xpath(selector)
            if links:
                link = links[0]
                break
        if link is None:
            continue
        target = link.get("href", "")
        titles = card.xpath('.//*[@data-test-id="result-title"]')
        title = (extract_text(titles[0]) if titles else extract_text(link)).strip()
        if not title or not safe_primary_result_url(target):
            continue
        # Direct outgoing result links only; never expose Ecosia click trackers.
        parsed = urlsplit(target)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() != "https" or host == "ecosia.org" or host.endswith(".ecosia.org"):
            continue
        if target in seen:
            continue
        seen.add(target)
        descriptions = card.xpath(
            './/*[contains(@class,"description") or contains(@class,"snippet") '
            'or @data-test-id="snippet" or @data-test-id="result-description"'
            ' or @data-test-id="web-result-description"]'
        )
        content = extract_text(descriptions[0]).strip() if descriptions else ""
        results.add(results.types.MainResult(url=target, title=title, content=content))
    return results
