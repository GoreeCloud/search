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
import re
from socket import inet_aton
import ssl
import sys
import time
from dataclasses import dataclass
from unicodedata import category as unicode_category
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


def safe_public_url(href: object) -> bool:
    """Check the reported URL without DNS, network access, or logging its contents."""
    if (not isinstance(href, str) or not href or len(href) > 4096
            or '\\' in href or any(ch.isspace() or ord(ch) <= 32 or ord(ch) == 127
                                    or unicode_category(ch) in ('Cc', 'Cf', 'Cs', 'Zl', 'Zp')
                                    for ch in href)):
        return False
    try:
        parsed = urlsplit(href)
        host, port = parsed.hostname, parsed.port
    except ValueError:
        return False
    if (parsed.scheme not in ('http', 'https') or not host
            or parsed.username is not None or parsed.password is not None
            or port == 0 or '%' in parsed.netloc):
        return False
    # Numeric IPv4 aliases such as 2130706433 and 0177.0.0.1 can resolve
    # to loopback despite not parsing with ipaddress.ip_address alone.
    try:
        return ipaddress.ip_address(inet_aton(host)).is_global
    except OSError:
        pass
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    try:
        ascii_host = host.encode('idna').decode('ascii').lower()
    except UnicodeError:
        return False
    labels = ascii_host.split('.')
    if (len(ascii_host) > 253 or ascii_host.endswith('.') or len(labels) < 2
            or labels[-1] in ('local', 'localhost', 'internal', 'lan', 'invalid',
                              'test', 'example', 'onion', 'arpa', 'localdomain',
                              'home', 'corp')):
        return False
    return all(1 <= len(label) <= 63 and re.fullmatch(
        r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', label) for label in labels)


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
            or sorted(selected) != sorted(test.engines)
            or type(metadata.get('selected_engine_count')) is not int
            or metadata.get('selected_engine_count') != len(test.engines)
            or metadata.get('selection_not_contact_confirmation') is not True):
        raise ValueError("selected search sources differ from request")
    represented = {}
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("non-object result")
        href = result.get("url")
        title = result.get("title")
        if not isinstance(title, str) or not title.strip() or not safe_public_url(href):
            raise ValueError("invalid public result link")
        engine, credited = result.get('engine'), result.get('engines')
        if (not isinstance(engine, str) or engine not in test.engines
                or not isinstance(credited, list) or not credited
                or any(not isinstance(name, str) or name not in test.engines
                       for name in credited)):
            raise ValueError("invalid result source attribution")
        for name in set([engine, *credited]):
            represented[name] = represented.get(name, 0) + 1
    represented = dict(sorted(represented.items()))
    reported_counts = metadata.get('represented_result_counts')
    if (not isinstance(reported_counts, dict)
            or any(type(value) is not int for value in reported_counts.values())
            or metadata.get('represented_engines') != list(represented)
            or reported_counts != represented
            or metadata.get('representation_not_contact_confirmation') is not True):
        raise ValueError('invalid result representation metadata')
    valid = len(results)
    # SearXNG's unresponsive_engines list can include exception messages,
    # URLs and provider-specific metadata. Never emit those raw fields.
    # Publish only approved engine labels already selected in this request.
    if any(not isinstance(item, (list, tuple)) or len(item) < 2
           or not isinstance(item[0], str) or item[0] not in test.engines
           or not isinstance(item[1], str) for item in failures):
        raise ValueError('invalid provider error attribution')
    safe_failed = sorted({item[0] for item in failures})
    if valid >= test.minimum_results:
        state = "partial_results_with_provider_error" if failures else "results_observed"
    elif valid == 0:
        state = "no_results_with_provider_error" if failures else "no_result_links"
    else:
        state = "below_minimum_with_provider_error" if failures else "below_minimum"
    return {
        "category": test.name,
        "result_links": valid,
        "unresponsive_engines": len(failures),
        "unresponsive_selected_engines": safe_failed,
        "state": state,
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
