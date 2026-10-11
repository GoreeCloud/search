# Official GoreeCloud Search homepage — desktop and mobile

**Status:** Owner-approved visual target, October 11, 2026. **Product status:** Development, not a publicly launched search service.

The owner supplied two official homepage mockups, one desktop (1440 × 900) and one tall mobile layout. The supplied mockups take precedence over the previous green/teal homepage styling in the private GoreeCloud Search consumer. The implementation is in `searx/templates/simple/index.html`, `simple_search.html`, `goreecloud_site_header.html`, `goreecloud_site_footer.html`, `searx/static/themes/simple/goreecloud-mockup.css` and `goreecloud-theme.js`.

## Visual reference and layout

- Soft near-white/ice-blue background, navy typography, vivid cobalt highlighting **Cloud**, cyan rounded-square magnifying-glass symbol, soft search-field shadow.
- Header: symbol, **GoreeCloud | Search** at left; About, Privacy, Open source ↗ and moon appearance control at right. Mobile reduces secondary navigation and retains Open source plus the moon control. Privacy/About remain accessible in the footer.
- Main: centered cyan icon; bold **GoreeCloud Search**; *Explore the web. Not your personal data.*; prominent white rounded input with search icon and blue arrow/submit button.
- Principles row: No tracking, No user profiles, Open source, Self-hostable. Two mockup links: **Why GoreeCloud Search?** anchors to the lower explanation, **View the project ↗** points to the GoreeCloud repository.
- Lower section: **Find more. Give away less.** above a concise privacy explanation, with clear development and provider limitations. Footer has the GoreeCloud copyright line and privacy, About, Preferences and GitHub links.
- Desktop layout uses a centered search column and one-line principles where space allows; mobile uses generous vertical spacing, a compact arrow-only submit button, wrapped principles and links, and a stacked footer. Layout must not overflow horizontally at 390 px or 1440 px.

## Functional boundaries preserved

This implementation is the *live source-connected local Development application*, not the static mockup's "Homepage concept — not a live service" badge. Its working search and no-network provider-preview buttons remain POST-only, with no query-bearing URLs. The only built-in search services are Brave Search and Startpage. The preview action is an additional unobtrusive text button below the two owner-designed links. Search results, preferences and safety errors keep the existing private policy gates. The private results search header also adopts a compact responsive search field, suppresses its duplicate upstream logo, and hides the redundant General-only category rail so the official masthead remains the single top-level identity. The moon control toggles an accessible light/dark override within the current browser tab only, with no analytics or external asset dependency.

Trust claims shown in the official mockup describe the project's privacy goals, **not independent certification**. Search terms may be sent to Brave Search or Startpage. The homepage's lower explanation and local privacy disclosure state this explicitly. There is no guarantee of anonymity, third-party non-tracking, or completed privacy/security and release acceptance; Startpage's upstream proof-of-work challenge remains a qualification gate.

## Validation

Run `python -m unittest discover -s tests/goreecloud -q` and the focused upstream regressions. Chrome synthetic browser CI checks both 1440 × 900 and 390 × 844, including header, visible logo and search, principle links, local theme toggle, no horizontal overflow, POST-only preview, and provider switching. Browser screenshots are CI evidence, not independent visual-conformance or assistive-technology certification. Keep Draft PR and review/release gates open until formally accepted.
