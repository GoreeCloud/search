# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bing-Images: description see :py:obj:`searx.engines.bing`."""

import typing as t
import json
from urllib.parse import urlencode

from searx.engines.bing import fetch_traits  # pylint: disable=unused-import
from searx.result_types import EngineResults

if t.TYPE_CHECKING:
    from searx.extended_types import SXNG_Response
    from searx.search.processors import OnlineParams


about = {
    "website": "https://www.bing.com/images",
    "wikidata_id": "Q182496",
    "official_api_documentation": "https://github.com/MicrosoftDocs/bing-docs",
    "use_official_api": False,
    "require_api_key": False,
    "results": "HTML",
}

categories = ["images", "web"]
paging = True
enable_http3 = True
safesearch = True
time_range_support = True
time_map = {
    "day": 60 * 24,
    "week": 60 * 24 * 7,
    "month": 60 * 24 * 31,
    "year": 60 * 24 * 365,
}

base_url = "https://www.bing.com"
"""Bing-Image search URL"""


def request(query: str, params: "OnlineParams"):
    """Assemble a Bing-Image request."""

    engine_region = traits.get_region(params["searxng_locale"], traits.all_locale)

    # build URL query / example:
    # https://www.bing.com/images/async?q=foo&mmasync=1&first=1&count=35

    query_params = {
        "q": query,
        "mmasync": "1",
        # to simplify the page count lets use the default of 35 images per page
        "first": (int(params.get("pageno", 1)) - 1) * 35 + 1,
        "count": 35,
    }

    if engine_region and engine_region != "clear":
        lang, _, cc = engine_region.partition("-")
        query_params["setlang"] = lang
        if cc:
            query_params["cc"] = cc

    # time range
    # - example: one year (525600 minutes) 'qft=filterui:age-lt525600'
    if params["time_range"]:
        query_params["qft"] = "filterui:age-lt%s" % time_map[params["time_range"]]

    params["url"] = base_url + "/images/async?" + urlencode(query_params)


def response(resp: "SXNG_Response") -> EngineResults:
    """Get response from Bing-Image"""

    res = EngineResults()

    dom = resp.html()

    for result in dom.xpath('//ul[contains(@class, "dgControl_list")]/li'):
        metadata_attrs = result.xpath('.//a[@class="iusc"]/@m')
        if not metadata_attrs:
            continue

        # A single incomplete/malformed card must not discard other images
        # returned by the provider. Do not log the source payload: it can
        # contain the searched terms and full provider/result URLs.
        try:
            metadata = json.loads(metadata_attrs[0])
        except json.JSONDecodeError:
            continue
        if not isinstance(metadata, dict) or any(
            not isinstance(metadata.get(field), str) or not metadata[field].strip()
            for field in ('purl', 'turl', 'murl')
        ):
            continue

        title = " ".join(result.xpath('.//div[@class="infnmpt"]//a/text()')).strip()
        if not title:
            title_attrs = result.xpath('.//div[@class="infnmpt"]//a/@title')
            title = next((label.strip() for label in title_attrs if label.strip()), '')
        if not title and isinstance(metadata.get('t'), str):
            title = metadata['t'].strip()
        if not title:
            continue

        img_format = " ".join(result.xpath('.//div[@class="imgpt"]/div/span/text()')).strip().split(" · ")
        source = " ".join(result.xpath('.//div[@class="imgpt"]//div[@class="lnkw"]//a/text()')).strip()

        res.add(
            res.types.Image(
                title=title,
                url=metadata["purl"],
                thumbnail_src=metadata["turl"],
                img_src=metadata["murl"],
                content=metadata.get("desc") if isinstance(metadata.get("desc"), str) else "",
                source=source,
                resolution=img_format[0],
                img_format=img_format[1] if len(img_format) >= 2 else "",
            )
        )
    return res
