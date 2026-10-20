# SPDX-License-Identifier: AGPL-3.0-or-later
"""Engine to search using the Brave (WEB) Search API.

.. _Brave Search API: https://api-dashboard.search.brave.com/documentation

Configuration
=============

The engine has the following mandatory setting:

- :py:obj:`api_key`

Optional settings are:

- :py:obj:`results_per_page`

.. code:: yaml

  - name: braveapi
    engine: braveapi
    api_key: 'YOUR-API-KEY'  # required
    results_per_page: 20     # optional

The API supports paging and time filters.
"""

import typing as t

from searx.exceptions import SearxEngineAPIException
from searx.goreecloud_policy import safe_external_media_url, safe_primary_result_url
from searx.result_types import EngineResults, MainResult

if t.TYPE_CHECKING:
    from searx.extended_types import SXNG_Response
    from searx.search.processors import OnlineParams

about = {
    "website": "https://api.search.brave.com/",
    "wikidata_id": None,
    "official_api_documentation": "https://api-dashboard.search.brave.com/api-reference/web/search/get",
    "use_official_api": True,
    "require_api_key": True,
    "results": "JSON",
}

api_key: str = ""
"""API key for Brave Search API (required)."""

categories = ["general", "web"]
paging = True
safesearch = True
safesearch_map = {2: "strict", 1: "moderate", 0: "off"}
time_range_support = True

results_per_page: int = 20
"""Maximum number of results per page (default 20)."""

base_url = "https://api.search.brave.com/res/v1/web/search"
"""Base URL for the Brave Search API."""

time_range_map = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}
"""Mapping of SearXNG time ranges to Brave API time ranges."""

max_page = 10


def setup(_: dict[str, t.Any]) -> bool | None:
    """Initialize the engine."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise SearxEngineAPIException("Brave API not configured")
    if type(results_per_page) is not int or not 1 <= results_per_page <= 20:
        raise SearxEngineAPIException("Invalid Brave API result count")
    if base_url != "https://api.search.brave.com/res/v1/web/search":
        raise SearxEngineAPIException("Unapproved Brave API endpoint")


def request(query: str, params: "OnlineParams") -> None:
    """Create the API request."""
    # Fail before forming any request if this dormant adapter is unconfigured.
    # Activating a paid, identifiable API account is a separate privacy decision.
    setup({})
    if not isinstance(query, str) or not query.strip() or len(query) > 600 or len(query.split()) > 75:
        raise SearxEngineAPIException("Brave API query exceeds provider limits")
    page = params["pageno"]
    if type(page) is not int or not 1 <= page <= max_page:
        raise SearxEngineAPIException("Brave API page out of range")

    search_args: dict[str, str | int | bool] = {
        "q": query,
        "count": results_per_page,
        "offset": page - 1,
        "text_decorations": False,
        "result_filter": "web",
    }
    if params["time_range"]:
        freshness = time_range_map.get(params["time_range"])
        if freshness is None:
            raise SearxEngineAPIException("Unsupported Brave API time range")
        search_args["freshness"] = freshness
    search_args["safesearch"] = safesearch_map.get(params["safesearch"], "off")

    # Official POST contract keeps raw search terms out of the URL and
    # reverse-proxy request-target logs. It does not stop Brave from
    # associating the account token with the submitted query.
    params["method"] = "POST"
    params["url"] = base_url
    params["json"] = search_args
    params["allow_redirects"] = False
    params["headers"]["X-Subscription-Token"] = api_key
    params["headers"]["Accept"] = "application/json"


def response(resp: "SXNG_Response") -> EngineResults:
    """Process the API response and return results."""
    data = resp.json()
    if not isinstance(data, dict):
        raise SearxEngineAPIException("Invalid Brave API response")
    web = data.get("web")
    if not isinstance(web, dict) or not isinstance(web.get("results"), list):
        raise SearxEngineAPIException("Invalid Brave API Web results")

    res = EngineResults()
    for item in web["results"]:
        if not isinstance(item, dict):
            raise SearxEngineAPIException("Invalid Brave API result item")
        url, title, description = item.get("url"), item.get("title"), item.get("description", "")
        if not isinstance(title, str) or not title.strip():
            raise SearxEngineAPIException("Invalid Brave API result title")
        if not isinstance(description, str):
            raise SearxEngineAPIException("Invalid Brave API result description")
        if not safe_primary_result_url(url) or not safe_external_media_url(url):
            raise SearxEngineAPIException("Unsafe Brave API result URL")
        res.add(MainResult(url=url, title=title, content=description))
    return res
