# SearXNG upstream provenance

GoreeCloud Search incorporates the source of [SearXNG](https://github.com/searxng/searxng) as its federated-search foundation.

- Import date: 2026-10-10.
- Upstream `master` commit: `f4822b3fc46726bb259d14c6332b702c76b98f82`.
- Source relationship: unrelated-history merge into a topic branch from GoreeCloud/search main; imported upstream snapshot and provenance are retained.
- License: AGPL-3.0-or-later; preserve the upstream [LICENSE](LICENSE), AUTHORS.rst, notices and applicable network source-availability obligations.
- GitHub metadata: `GoreeCloud/search` existed before import, so this is a source-code fork, **not** a GitHub-native fork relationship.
- Update strategy: track upstream through `https://github.com/searxng/searxng.git` and merge vetted updates. Do not automatically enable upstream CI/release jobs in the GoreeCloud repository.

The former GoreeCloud-native Search implementation remains in historical repository branches. It is not silently restored to current main, included in this SearXNG engine, or Production-qualified.
