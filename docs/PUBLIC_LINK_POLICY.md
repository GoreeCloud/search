# GoreeCloud Search — Public navigation-link policy

**Status:** Original, dependency-free Development validation; no web crawling, fetching or link previews. [Draft PR #2](https://github.com/GoreeCloud/search/pull/2) remains unmerged.

## One policy for every result source

`goreecloud_search/links.py` contains `public_https_url`. The private catalog `safe_url` and optional Brave/SearXNG normalization both call this same function, rather than maintaining separate hostname rules.

The function accepts a bounded (at most 2048-character), uncredentialed **HTTPS** navigation URL on the standard port 443, without network or DNS lookups. It returns the original URL unchanged when accepted. It rejects non-HTTPS schemes, embedded username/password, unsupported port numbers, bad authority encodings, local or special-use domains, single-label hostnames, malformed DNS names, non-global IP literals and ambiguous numeric-host forms that a browser could interpret as an IP address.

The policy is **not** proof that an apparently public DNS hostname cannot resolve to a private address later. DNS rebinding and downstream browser navigation/network policy remain outside this validator's guarantee. Neither the HTTP search backend nor these adapters fetches a result URL: the link is displayed for a user's explicit navigation.

## Verified source contracts

Seven offline `tests/test_links.py` tests verify:

- Valid public HTTPS and IDN/IPv6 links retain their exact original value in the local and optional-provider adapters.
- Local/special-use suffixes and private or browser-normalized numeric hosts are rejected consistently.
- Malformed authorities, nonstandard ports, credentials and non-HTTPS schemes fail closed.
- Unsafe remote search results are filtered out of a mocked Brave response, without making a real provider call.
- An invalid local JSONL import cannot replace the existing private SQLite index.

The code uses only the Python standard library. The optional native GTK4 development archive now includes `links.py` because the local index depends on it; the existing packaged-launcher acceptance test catches omissions of required first-party modules.

## Still open

Browser-side independent URL vetting, any required external link reputation checks, live-provider terms/billing acceptance, redirect behavior after a user clicks a link, broader IDN/homograph reviews, accessibility of link titles and full native packaging remain future engineering gates. Do not interpret static link validation as safe-browsing certification. No production service or paid provider was enabled.
