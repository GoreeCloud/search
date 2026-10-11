# GoreeCloud Search

Privacy-focused, configurable federated search rebuilt from the SearXNG source engine toward GoreeCloud platform standards.

**Lifecycle:** Development only. **Upstream:** SearXNG `f4822b3`. **Glaze:** V1.7 / 1.7.0 inherited foundation, partial mapping (not formally accepted).

## Working implementation

The codebase includes SearXNG's federated engine adapters, categorized web/image/video/news discovery, result aggregation, preferences, HTML search, and machine-readable JSON search (enabled by the provided private profile). GoreeCloud additions include the first semantic Glaze interface layer, a local-only privacy configuration, and a source/contract validation gate. No independent Index, AI answers, local business knowledge, or alert system is implied.

## Develop locally

Follow [upstream SearXNG development instructions](docs/dev/index.rst) to install dependencies. Set a unique 32+-character secret in a local secret store, and launch through the fail-closed wrapper:

```sh
export SEARXNG_SECRET="<unique-strong-secret-from-your-secret-store>"
./scripts/run-private.sh
```

Never use the upstream placeholder key. The profile binds **127.0.0.1**, disables metrics and remote autocomplete, proxies images, defaults to POST, and exposes opt-in JSON on a private interface. It does **not** implement public rate limiting. Internet exposure requires a separate gated HTTPS/reverse-proxy, Valkey limiter, hardened secrets, security/privacy and operational acceptance.

## Private search disclosure safeguards

The local profile now rejects query-bearing GET requests, preserves POST even on Android/WebKit, and disables caching for private search pages. Query-length and distinct-provider limits are set to 512 characters and 32 engines respectively; searches exceeding these limits return 413/422 rather than silently expanding disclosure. Private result pages omit query-bearing RSS/share URL metadata. The privacy-sensitive preferences for POST transport, title disclosure, autocomplete, favicons, and image proxy are locked against cookie and request overrides. These protections cannot prevent configured upstream providers from receiving queries, and they do not establish anonymity or production security acceptance.

## Development validation

With SearXNG's pinned requirements installed (including the Python 3.10 compatibility backport when applicable), run:

```sh
python -m compileall -q searx
python -m unittest discover -s tests/goreecloud -v
```

The 2026-10-10 local verification passed 18 focused foundation, privacy, and runtime tests, with the Flask homepage and three local CSS/privacy assets returning HTTP 200. No live provider searches, device/browser acceptance, full upstream regression suite, or production security acceptance have been verified. This local environment also logged SQLite threading warnings and failures loading the optional Ahmia and Torch engines; provider availability remains a separate qualification requirement.

## Source boundaries

- [SearXNG provenance and AGPL obligations](UPSTREAM.md)
- [Partial Glaze implementation and acceptance gaps](GLAZE-INTEGRATION.md)
- [Capability roadmap](docs/goreecloud/ROADMAP.md)
- [Upstream SearXNG documentation](README.rst)

Pre-reset GoreeCloud Search code persists on historic branches; this import does not automatically provide or authorize GoreeCloud Index, Identity, Privacy Shield, Wardveil Security, or Everkeep integration.
