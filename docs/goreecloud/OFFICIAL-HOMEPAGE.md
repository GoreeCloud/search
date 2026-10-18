# Official GoreeCloud Search homepage — desktop and mobile

**Status:** Historical owner-approved visual baseline, October 11, 2026; subsequent Development results-first, category, Settings and Qwant work supersedes prior quick-action details. **Product status:** Development, not a publicly launched search service.

The owner supplied two official homepage mockups, one desktop (1440 × 900) and one tall mobile layout. The supplied mockups take precedence over the previous green/teal homepage styling in the private GoreeCloud Search consumer. The implementation is in `searx/templates/simple/index.html`, `simple_search.html`, `goreecloud_site_header.html`, `goreecloud_site_footer.html`, `searx/static/themes/simple/goreecloud-mockup.css` and `goreecloud-theme.js`.

## Visual reference and layout

- Soft near-white/ice-blue background, navy typography, vivid cobalt highlighting **Cloud**, cyan rounded-square magnifying-glass symbol, soft search-field shadow.
- Header: symbol, **GoreeCloud | Search** at left; About, Privacy, Open source ↗ and moon appearance control at right. Mobile reduces secondary navigation and retains Open source plus the moon control. Privacy/About remain accessible in the footer.
- Main: centered cyan icon; bold **GoreeCloud Search**; *Explore the web. Not your personal data.*; prominent white rounded input with search icon and blue arrow/submit button.
- Principles row: No tracking, No user profiles, Open source, Self-hostable. Two mockup links: **Why GoreeCloud Search?** anchors to the lower explanation, **View the project ↗** points to the GoreeCloud repository.
- Lower section: **Find more. Give away less.** above a concise privacy explanation, with clear development and provider limitations. Footer has the GoreeCloud copyright line and privacy, About, Preferences and GitHub links.
- Desktop layout uses a centered search column and one-line principles where space allows; mobile uses generous vertical spacing, a compact arrow-only submit button, wrapped principles and links, and a stacked footer. Layout must not overflow horizontally at 1440 px, 768 px, 390 px, or narrow 320 px viewports. The 320 px fallback retains the moon toggle and an accessible 44 px GitHub source link, shortening only the link's visible label.

## Functional boundaries preserved

The mockup was implemented in the private Development app, not merely as a static sample. **Current candidate update:** the homepage now shows one primary POST search action without provider quick buttons or a preview shortcut; provider choice moved into Settings, while `POST /preview` remains a local no-network contract. Approved source families are Brave, Startpage and Qwant, with Web/Images/Videos/News tabs on results. Search, preferences and policy-error pages retain their local guards. The responsive masthead, accessible skip link, theme control and keyboard search focus remain; rendered accessibility/device conformance is still an open gate.

The historical mockup's privacy claims describe goals, not independent certification. Approved requests can disclose query terms to Brave, Startpage and Qwant. There is no independent anonymity or third-party non-tracking guarantee, and provider access restrictions remain unqualified. `POST /preview` inspects local selections without provider calls; the current homepage does not advertise it as a primary action.

## Historical one-provider homepage actions (superseded)

An earlier candidate displayed provider-specific Brave and Startpage search buttons and a preview shortcut. This behavior was **superseded** by the results-first owner direction: the current Development homepage has one primary search action, and source selection resides in Settings. The historical smoke tests for these buttons are not the acceptance definition for the current candidate.

## Validation

Run `python -m unittest discover -s tests/goreecloud -q` and the focused upstream regressions. Chrome synthetic browser CI checks both 1440 × 900 and 390 × 844, including header, visible logo and search, principle links, local theme toggle, no horizontal overflow, POST-only preview, and provider switching. Browser screenshots are CI evidence, not independent visual-conformance or assistive-technology certification. Keep Draft PR and review/release gates open until formally accepted.
