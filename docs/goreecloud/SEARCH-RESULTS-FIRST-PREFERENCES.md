# GoreeCloud Search — Results-first UX and browser-local engines

**Scope:** Private, loopback-only Development candidate; originally introduced in Search draft PR #16 and subsequently expanded by PR #18. User-requested redesign of the homepage and web results, stacked on the existing Search UI draft branch. No public release or production configuration change.

## Experience

- The homepage search form offers one primary search action; it does not show Brave Search/Startpage buttons or the source-preview shortcut.
- The standard Preferences page (General) provides an explicit, persistent choice: **All sources** (default), **Brave Search only**, **Startpage only**, **Qwant only**. A Settings link in the header opens the page.
- Search result tabs offer Web, Images, Videos and News with only approved Brave/Startpage/Qwant variants. Startpage-only disables Videos because no Startpage video adapter is configured.
- Search results occupy the first main content column. Provider attribution, errors and manual same-source retry remain in a secondary collapsible section. Partial failures retain a visible, compact inline notice near the result heading. Empty-result errors retain an accessible on-page recovery action.
- On small screens, the header uses accessible icon controls; the 320px and 390px Chromium viewport smoke checks explicitly reject horizontal scroll. Navigation remains keyboard-operable.

## Privacy and saved choice

The selected engine preference is stored in a host-only browser cookie named `goreecloud_search_sources`. Only `both` (the persisted key for all approved sources), `brave`, `startpage` and `qwant` are accepted. It is `HttpOnly`, `SameSite=Lax`, has a finite max age, and gains `Secure` on HTTPS. No user profile or search-term history is introduced.

A normal search submits its terms with POST, never as an address-bar query parameter. If the request explicitly selects approved engines, that selection wins over the cookie. Supported `!bang` searches preserve their intended explicitly selected source. No disallowed engines or automatic provider fallback are introduced.

The upstream Preferences page contains an optional serialized-preferences input, blank during ordinary saving. The private request guard permits the blank value and continues to reject all nonempty serialized preference imports and URL-based preference imports. Browser smoke and isolated security tests cover this regression.

## Verification performed in Development

- 142 GoreeCloud Python tests passing on the current three-provider candidate, including browser-local preference save, input validation, empty serialized-field submission and blocked nonempty imports.
- 72 targeted upstream SearXNG tests passing.
- Chromium synthetic/no-provider-traffic smoke passed after fixing Settings header overflow and local Preferences submit: desktop 1440, tablet 768, phone 390 and narrow phone 320, both light/dark modes, keyboard POST submission, same-source retry, results-first responsive columns, no horizontal scrolling, no query parameters in the address bar.

The test browser uses synthetic provider responses. Passing browser tests do **not** establish Brave/Startpage/Qwant real-world availability, target-device hardware approval, public authentication/rate limiting, or production security. The actual Linux preview and source commit must be reverified at the draft PR's exact head. Existing development SQLite multithread warnings and missing private rate-limiter configuration remain documented; do not suppress them to claim Stable.

**Rollback:** revert the reviewed feature commit(s) on the development branch. The changes introduce one optional client-side cookie and no new database tables or migrations. The browser cookie naturally expires or can be cleared using browser cookie controls.
