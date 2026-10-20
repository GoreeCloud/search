# GoreeCloud Search

**Lifecycle:** Development — **not** a Stable or public production release.

GoreeCloud Search is an open-source privacy-oriented metasearch project. Its current development implementation builds on SearXNG, with work on private search-provider routing, category-specific results, a separate opt-in native document index, and GoreeCloud UI integration.

## Source-of-truth notice

As verified on October 19, 2026, the `main` branch contains **this README only**. It does **not** contain a buildable Search application, deployment configuration, or the CI workflows used to validate the development implementation. Do not treat `main`, this repository description, a green development-branch check, or an existing private container as proof of Stable readiness.

Current implementation work resides in development branches and stacked pull requests. Relevant work includes:

- [Private Development baseline and safeguards — PR #22](https://github.com/GoreeCloud/search/pull/22)
- [Native document index — PR #23](https://github.com/GoreeCloud/search/pull/23)
- [Development UI and privacy flow — PR #25](https://github.com/GoreeCloud/search/pull/25)
- [Provider timeout handling — PR #27](https://github.com/GoreeCloud/search/pull/27)
- [Startpage parser hardening — PR #28](https://github.com/GoreeCloud/search/pull/28)
- [Seven-provider federation candidate — PR #29](https://github.com/GoreeCloud/search/pull/29)

These branches are **not automatically integrated** and may not represent the exact privately deployed image. Consult the current GitHub heads, review state, workflow runs and deployment evidence rather than these historical links alone.

## Development and acceptance boundaries

[Source consolidation and private deployment provenance — issue #33](https://github.com/GoreeCloud/search/issues/33) is the primary integration gate. [Provider reliability — issue #26](https://github.com/GoreeCloud/search/issues/26) and [redirect/SSRF egress security — issue #21](https://github.com/GoreeCloud/search/issues/21) remain tracked acceptance concerns.

The private Development environment is documented as `search-dev.goreecloud.com` over an approved private network; **this README does not independently verify its current health**. `search.goreecloud.com` is reserved for qualified Stable use, not a fallback destination for development traffic.

Before any promotion, qualify the **exact integrated source head** and deployed image, required CI, provider-specific successes and failures, private and Tor-mediated egress with fail-closed behavior, DNS and redirect security, rate limiting, resilient error messaging, native-index scope disclosure, client/mobile accessibility, recoverability and authenticated private access. Never silently substitute a denied upstream provider, route private queries directly through the client, broaden public exposure, or treat a native-index result as general-web coverage.

All interface and icon work must follow [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui), the exclusive active design authority. Legacy Glaze/Glaze UI must not be adopted for new or revised work.

This is a **source-navigation and safety notice**, not a deployment or product-release announcement.
