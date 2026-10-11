# Glaze adoption — GoreeCloud Search

**Development-only, partial consumer mapping. Not accepted as current Glaze-conformant, Production, or Stable.**

- Governing system: GoreeCloud/glaze, Official Anchor **Glaze V1.7 / 1.7.0**.
- CSS provenance: `GoreeCloud/glaze` commit `0798de28fe0626d6cc8bd7986dc9c4b922119c35`. The inherited Glaze V1.4.1 CSS import graph is locally packaged under `searx/static/themes/simple/glaze/css`.
- Working mapping: semantic content versus interactive chrome, opaque result cards, GoreeCloud search-header identity, selected-source disclosure, actionable empty states, accessible search labeling and local styling; focus-visible states, system/light/dark themes, RTL inherited from SearXNG, responsive scaling, Reduced Motion, Reduced Transparency, and Forced Colors fallback. Rendering is tested through the Flask test client, not in a full browser.
- Browser smoke: a separate CI job checks a synthetic, loopback-only homepage at desktop (1440px) and phone (390px) widths with local CSS, POST form, disclosure, horizontal-overflow and dark-background assertions. Screenshots are retained for seven days. This automated smoke is *not* complete visual, accessibility or Glaze consumer acceptance, and its actual CI result must be verified at the exact candidate head.
- Non-claims: no Glaze JS runtime activation; no full exact-revision rendered acceptance, human assistive-technology validation, production-grade performance or full consumer registration/acceptance; no deployment or publication authorization.

The packaged Glaze CSS retains its [MIT license](docs/licenses/GLAZE-MIT-LICENSE). The browser UI has no GoreeCloud-added trackers, remote fonts, third-party icon packs, or scripting requirement. Presentation does not grant underlying privacy/security/identity provider authority.
