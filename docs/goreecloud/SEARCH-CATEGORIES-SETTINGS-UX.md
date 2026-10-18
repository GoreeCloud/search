# GoreeCloud Search — Settings and category navigation

**Scope:** Development-only category and Settings capability. First introduced by Search draft PR #17 and expanded by stacked PR #18 to three provider families; the All Sources feature adds four more. The owner approved the uncluttered homepage direction but rejected the upstream Settings visual treatment and requested Web, Images, Videos and News choices.

## Settings

The private Settings page uses the GoreeCloud Search identity, without the inherited oversized SearXNG logo, and adopts the Glaze-consumer canvas/surface typography, tab rail, card-like groups, primary Save and secondary Back/Reset actions. Smaller layouts use two rows of three tabs rather than six full-width stacked tabs. Original preference inputs, radio persistence, optional private import protections and theme behaviors remain operational.

## Supported categories and source ownership

- **Web:** Brave Search, Startpage, Qwant, DuckDuckGo, Ecosia, Bing and Google.
- **Images:** Brave Search, Startpage, Qwant, DuckDuckGo, Bing and Google.
- **Videos:** Brave Search, Qwant, DuckDuckGo, Bing and Google.
- **News:** Brave Search, Startpage, Qwant, DuckDuckGo, Bing and Google.

Only 24 approved SearXNG adapter instances from **seven provider families** are enabled. Unapproved inherited engines, Maps and Shopping sources remain excluded. Web, Images, Videos and News navigation submits query and engine selections via same-origin POST; query terms never enter a GET URL. Fanout is capped at seven selected provider families.

The default **All Sources** preference selects all approved adapters available for the chosen category. Videos includes Brave Search, Qwant, DuckDuckGo, Bing and Google; Startpage and Ecosia single-source selections disable Videos and are rejected rather than silently substituted. Ecosia also has no Images or News adapter. Saved source choices remain distinct from per-query explicit selections. This is source-contract behavior, not proof that providers are reachable.

## Verification

Category contract/unit tests use a patched offline executor and verify adapter names, saved-source compatibility, intentional rejection paths, POST forms, client-side unavailability, page attribution and absence of query terms in URL parameters. Chromium smoke covers actual POST category switching plus desktop, phone, small-phone Settings tabs and responsive Search results. This is synthetic-browser and development-only evidence, not real image/video/news provider success.

**Release blockers:** real provider connectivity may be challenged/rate-limited; private listener has no public auth or rate limiting, and SQLite runtime warnings persist. Do not advertise public availability, merge or deploy without applicable owner release gates.

**Rollback:** revert this development feature branch's commits. No database migration or user data change is involved.
