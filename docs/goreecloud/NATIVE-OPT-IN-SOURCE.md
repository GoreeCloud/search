# Native index opt-in source (Development only)

The native source is disabled unless both
`GOREECLOUD_NATIVE_SOURCE_ENABLED=1` and
`GOREECLOUD_NATIVE_INDEX_PATH=/absolute/approved.db` are set.

Create the database offline using `python3 -m native_search import-approved-repo`
with the reviewed corpus manifest and pinned Git revision. Mount the index
read-only in the private Development application.

Users must explicitly choose **Search native index**. Queries use POST, with
no URL query parameters and no Brave/Qwant/Startpage fallback. The route is
limited to owner-reviewed GitHub documents; it is not a general web crawler.
It does not edit saved provider preferences or begin a background crawl.

Do not enable without validating the selected corpus, NetBird-only access,
read-only permissions, smoke tests, backup and rollback. Unset the enable
variable to disable the route and hide the native control without changing
the existing federated search configuration.
