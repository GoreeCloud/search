# GoreeCloud Search identity — Development candidate

**Status:** Development artwork, awaiting owner visual approval and official Glaze consumer review.

## Design

The product mark combines a white, open **G**-shaped search lens, a cyan discovery sparkle, and a short light-blue search handle on a rounded cyan-to-cobalt gradient tile. It replaces the previous generic magnifying glass and unifies the light/dark interface treatment.

The identity remains recognizable at browser-tab scale and in the 34px header mark, and it scales to the 72–80px homepage hero.

## Authoritative assets

- `searx/static/themes/simple/img/favicon.svg` is the canonical, local, script-free vector artwork.
- `searx/static/themes/simple/img/192.png` and `512.png` are corresponding deterministic raster exports from that SVG, kept for web-app manifest compatibility.
- The site header, homepage hero, browser favicon, and web-app manifest all point to these local resources using the `search-identity-2` cache key.
- Branding imagery is decorative within the page (`aria-hidden`, empty image alt); the adjacent product name and accessible home-link label identify GoreeCloud Search.

## Change and validation constraints

The new artwork is scoped to the Search product. Its colors reference the current GoreeCloud cyan/cobalt palette; it does not establish formal Glaze approval. No new remote assets, scripts, tracking, or provider connections are introduced.

On any future design revision, update all three exported files together, increment the cache key on the shared SVG and manifest icons, and rerun the asset, responsiveness, and browser checks. Do not substitute a mismatched PNG fallback.

**No production promotion, repository merge, or device acceptance is implied by this document.**
