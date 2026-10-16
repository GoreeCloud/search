# GoreeCloud Search — Results experience redesign

**Environment:** Development UI candidate, private/local SearXNG consumer only. This change does not alter Brave Search/Startpage adapters, backend selection, rankings, snippets, response payloads, search network traffic or public readiness.

## Problem observed

The owner-provided desktop screenshot exposed results constrained to a very narrow column, large unused margins, tiny linked titles/snippets, excessive boxed source controls, repeated error surfaces and a cramped sidebar. These symptoms occur despite the working home page and search query POST path.

## Implemented direction

- Apply a scoped, final-loaded `goreecloud-results.css` only in the private GoreeCloud Search profile and only to the results endpoint.
- Use a responsive main column and bounded sidebar: readable primary results take most of the available width; source messages and download controls remain secondary.
- Format results as calmer cards with 18–21px linked titles, readable snippets, restrained source labels, stronger information hierarchy and consistent spacing.
- Group the provider-failure notice with its explicit same-source POST retry; never hide an error, retry automatically, or imply a blocked provider worked.
- Preserve the exact selected-provider counts and attribution explanations in a disclosure that the user can expand. Provider switches remain dedicated POST forms and never leak search terms in the URL.
- Add an honest `Web results` heading with only a **count of displayed results on this page**, not an invented total count or provider availability estimate.
- Stack results, pagination and diagnostics on narrower screens, avoiding horizontal overflow at 320px–390px and preserving visible focus states, reduced motion and high-contrast fallback.

## Verification and gates

New browser smoke uses eight offline synthetic result objects to assert actual desktop/phone layout dimensions, mobile absence of horizontal scrolling, source details, provider action preservation and synthetic result rendering. Existing GoreeCloud privacy and backend tests must remain green. Screenshots from the test runner are disposable development evidence, not official Glaze acceptance.

Owner visual review at the private development URL, independent Glaze accessibility review, dark-mode physical-device acceptance, and the separate approved-provider reliability/public security gates remain open. This PR must stay draft until verified and accepted. No production deployment or external reviewer is imposed unless applicable repository protections require it.
