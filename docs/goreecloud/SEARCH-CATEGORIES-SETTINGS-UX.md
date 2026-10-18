# GoreeCloud Search — Settings and category navigation

**Scope:** Development-only category and Settings capability. First introduced by Search draft PR #17 and expanded by stacked PR #18 to three approved provider families. The owner approved the uncluttered homepage direction but rejected the upstream Settings visual treatment and requested Web, Images, Videos and News choices.

## Settings

The private Settings page uses the GoreeCloud Search identity, without the inherited oversized SearXNG logo, and adopts the Glaze-consumer canvas/surface typography, tab rail, card-like groups, primary Save and secondary Back/Reset actions. Smaller layouts use two rows of three tabs rather than six full-width stacked tabs. Original preference inputs, radio persistence, optional private import protections and theme behaviors remain operational.

## Supported categories and source ownership

- **Web:** Brave Search, Startpage and Qwant.
- **Images:** Brave Search Images, Startpage Images and Qwant Images.
- **Videos:** Brave Search Videos and Qwant Videos.
- **News:** Brave Search News, Startpage News and Qwant News.

Only eleven approved SearXNG adapter instances from **three provider families** are enabled. Other inherited engines and separate Google/Bing/Maps/Shopping sources are excluded. Web, Images, Videos and News navigation submits query and engine selections via same-origin POST; query terms never enter a GET URL. Fanout is capped at three selected provider families.

The default **All sources** preference selects all available approved sources for the chosen category. Videos includes Brave and Qwant only; Startpage-only disables Videos and a direct Startpage-only video request is rejected rather than silently substituted. Saved source choices remain distinct from per-query explicit selections. This is source-contract behavior, not proof that providers are reachable.

## Verification

Category contract/unit tests use a patched offline executor and verify adapter names, saved-source compatibility, intentional rejection paths, POST forms, client-side unavailability, page attribution and absence of query terms in URL parameters. Chromium smoke covers actual POST category switching plus desktop, phone, small-phone Settings tabs and responsive Search results. This is synthetic-browser and development-only evidence, not real image/video/news provider success.

**Release blockers:** real provider connectivity may be challenged/rate-limited; private listener has no public auth or rate limiting, and SQLite runtime warnings persist. Do not advertise public availability, merge or deploy without applicable owner release gates.

**Rollback:** revert this development feature branch's commits. No database migration or user data change is involved.
