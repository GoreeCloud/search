# GoreeCloud Search — Settings and category navigation

**Scope:** Development-only visual and category capability enhancement, stacked on Search draft PR #16. The owner approved the uncluttered homepage direction but rejected the upstream Settings visual treatment and requested Web, Images, Videos and News choices.

## Settings

The private Settings page uses the GoreeCloud Search identity, without the inherited oversized SearXNG logo, and adopts the Glaze-consumer canvas/surface typography, tab rail, card-like groups, primary Save and secondary Back/Reset actions. Smaller layouts use two rows of three tabs rather than six full-width stacked tabs. Original preference inputs, radio persistence, optional private import protections and theme behaviors remain operational.

## Supported categories and source ownership

- **Web:** Brave Search and Startpage.
- **Images:** Brave Search Images and Startpage Images.
- **Videos:** Brave Search Videos only.
- **News:** Brave Search News and Startpage News.

Only seven named SearXNG adapter *instances* from the same two approved provider families are enabled. No Google, Bing, alternative engine, third-party media API, Maps or Shopping adapter is authorized. The category menu submits query, category and mapped engine names via same-origin POST. No query is placed in a GET URL. Category fanout remains at most two adapter instances per search.

The user preference Both searches all available approved sources for that category, meaning Brave alone for Videos. A Startpage-only preference disables Videos in the UI and rejects a direct Startpage-only video request with HTTP 422; this is not an automatic substitution. The empty unsupported selector is not executable. No live provider viability is implied.

## Verification

Category contract/unit tests use a patched offline executor and verify adapter names, saved-source compatibility, intentional rejection paths, POST forms, client-side unavailability, page attribution and absence of query terms in URL parameters. Chromium smoke covers actual POST category switching plus desktop, phone, small-phone Settings tabs and responsive Search results. This is synthetic-browser and development-only evidence, not real image/video/news provider success.

**Release blockers:** real provider connectivity may be challenged/rate-limited; private listener has no public auth or rate limiting, and SQLite runtime warnings persist. Do not advertise public availability, merge or deploy without applicable owner release gates.

**Rollback:** revert this development feature branch's commits. No database migration or user data change is involved.
