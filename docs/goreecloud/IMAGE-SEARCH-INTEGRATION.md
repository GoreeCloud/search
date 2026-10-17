# GoreeCloud Search image service integration

**Status: private Development profile only; not deployed publicly.**

GoreeCloud Image Search embeds the GoreeCloud Search **client integration**
on web, Linux and Android, not a bundled Python/SearXNG server in the APK.
The backend is the GoreeCloud-controlled SearXNG fork. It accepts image queries
via POST /search with form fields q, categories=images, format=json, pageno
and safesearch. It returns standard SearXNG JSON image records.

The new configs/goreecloud/image-search-settings.yml uses the existing
Brave Images, Bing Images and DuckDuckGo Images adapters in an isolated
loopback profile. The main two-provider private web-search profile is untouched.
Start the image profile through scripts/run-images-private.sh with a
protected, unique 32+ character SEARXNG_SECRET from the approved secret store.

The app enables this source by default. A build-time
VITE_GOREECLOUD_SEARCH_IMAGES_URL selects the approved HTTPS endpoint.
The intended search.goreecloud.com name is **not DNS-confirmed** and is not
represented as a live service. Browsers require restricted, explicit CORS;
mobile/desktop require HTTPS. The client must never log queries, send
credentials, or silently fallback to a third-party instance.

Before exposing the service: qualify TLS/DNS, secrets, request limits,
abuse protections, legal upstream-engine terms, expected CORS origins,
image proxy, privacy boundaries, runtime response schema and real-device QA.
Unavailable web search must not block existing freely accessible collections.
General-web image copyright and reuse status must be visible in the UI.
