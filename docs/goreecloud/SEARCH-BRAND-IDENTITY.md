# GoreeCloud Search brand artwork — Development candidate, revision 3

**Status:** Design revision for owner review. Replaces the rejected gradient G/search lens and sparkle of revision 2. This is a source-level SVG change, not a generated chat image or approved Glaze identity.

## Visual treatment

The mark is a single bold search lens and short 45° handle in white, centered on a solid GoreeCloud cyan (#13BFD4) rounded square. It has no letters, gradients, stars, shadows inside the source, embossed surfaces or tiny details that compete at 16–34px. Visual simplicity and alignment with the adjacent GoreeCloud wordmark take priority over decorative symbolism.

## Consistency and maintenance

- The canonical local, script-free vector lives at `searx/static/themes/simple/img/favicon.svg`.
- The homepage hero, header and browser tab load the same asset with cache key `search-identity-3`.
- The 192px and 512px installable web-app icon PNGs are generated directly from this exact SVG using an isolated development rasterizer.
- Adjacent accessible text identifies the product, while repeated decorative images have empty alt text and `aria-hidden`.
- The SVG shape remains color-independent of light/dark theme and compatible with the existing rounded layout. Forced-colors remains under the Glaze visual acceptance gate.

The v2 revision was rejected by the owner after inspecting the actual laptop screenshot; no approval is implied for v3. The icon is now a restrained working proposal rather than a claim of unique trademark identity. Any formal visual identity change needs owner approval, Glaze design review, accessibility checks at favicon and app-icon sizes, and eventual trademark differentiation review if required.

No production deployment, PR merge, alternate provider, tracking mechanism or external asset is introduced.
