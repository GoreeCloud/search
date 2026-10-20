#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded HTTPS-only smoke test for GoreeCloud's FREE SearXNG categories.

Run only on an authorized NetBird-connected machine. No third-party API calls,
cookies, result storage, arbitrary URLs, query logging or redirect follow-up.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import ssl
import sys
import time
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener


ORIGIN = "https://search-dev.goreecloud.com"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class Category:
    name: str
    engines: tuple[str, ...]
    category_field: str
    synthetic_query: str
    minimum_results: int


CATEGORIES = {
    "general": Category("general", ("duckduckgo", "bing", "startpage"), "category_general",
                        "public library digital collection resources", 5),
    "images": Category("images", ("duckduckgo images", "bing images"), "category_images",
                       "NASA public domain space photos", 5),
    "videos": Category("videos", ("duckduckgo videos", "bing videos"), "category_videos",
                       "NASA Artemis science mission documentary", 5),
    "news": Category("news", ("duckduckgo news",), "category_news",
                     "NASA Artemis", 3),
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        # Never transmit search terms or credentials to a redirected origin.
        return None


def client():
    # Bypass environment-provided proxies and verify the real HTTPS certificate.
    return build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())


def build_search_request(test: Category) -> Request:
    body = urlencode({
        "q": test.synthetic_query,
        "engines": ",".join(test.engines),
        "language": "en",
        "format": "json",
        test.category_field: "1",
    }).encode("ascii")
    return Request(
        ORIGIN + "/search", data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"},
    )


def inspect_results(raw: bytes, test: Category) -> dict:
    """Fail closed on malformed/misattributed responses; return aggregate counts only."""
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("invalid response JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("result document is not an object")
    metadata = payload.get("goreecloud")
    results = payload.get("results")
    failures = payload.get("unresponsive_engines")
    if not isinstance(metadata, dict) or not isinstance(results, list) or not isinstance(failures, list):
        raise ValueError("incomplete search response")
    selected = metadata.get("selected_engines")
    if (not isinstance(selected, list) or any(not isinstance(x, str) for x in selected)
            or sorted(selected) != sorted(test.engines)):
        raise ValueError("selected search sources differ from request")
    valid = 0
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("non-object result")
        href = result.get("url")
        title = result.get("title")
        if not isinstance(href, str) or not isinstance(title, str):
            continue
        if not title.strip() or any(ord(x) < 32 for x in href):
            continue
        try:
            url = urlsplit(href)
            host = url.hostname
            port = url.port
        except ValueError:
            continue
        if (url.scheme.lower() not in ("http", "https") or not host
                or port == 0 or url.username or url.password
                or host.casefold().rstrip(".") == "localhost"
                or host.casefold().endswith(".local")):
            continue
        try:
            literal_ip = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if not literal_ip.is_global:
                continue
        valid += 1
    return {
        "category": test.name,
        "result_links": valid,
        "unresponsive_engines": len(failures),
        "state": "results_observed" if valid >= test.minimum_results else
                 ("no_result_links" if valid == 0 else "below_minimum"),
    }


def run(category_names: tuple[str, ...], *, opener=None, nap=time.sleep) -> tuple[list[dict], bool]:
    opener = opener or client()
    with opener.open(Request(ORIGIN + "/readyz", method="GET"), timeout=8) as ready:
        if ready.status != 200 or ready.read(64).strip() != b"READY":
            raise ValueError("readiness response failed")
    print("HTTPS_READINESS_PASS", flush=True)
    records = []
    for index, name in enumerate(category_names):
        if index:
            nap(1)
        category = CATEGORIES[name]
        with opener.open(build_search_request(category), timeout=35) as response:
            if response.status != 200:
                raise ValueError("search endpoint returned non-200 response")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("oversized search response")
        result = inspect_results(raw, category)
        records.append(result)
        # Print no queries, user identifiers, raw result URLs or provider error messages.
        print(json.dumps(result, sort_keys=True), flush=True)
    return records, all(r["state"] == "results_observed" for r in records)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="One bounded free Search category health check")
    parser.add_argument("--category", choices=tuple(CATEGORIES), action="append",
                        help="Restrict to a category (defaults to all four, one request each)")
    args = parser.parse_args(argv)
    names = tuple(dict.fromkeys(args.category or tuple(CATEGORIES)))
    try:
        _, healthy = run(names)
    except Exception as error:
        # Do not leak URL, request payload, response body, or credentials in logs.
        print("CATEGORY_SMOKE_ERROR", type(error).__name__, file=sys.stderr)
        return 2
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
