# GoreeCloud Search — Connector status

The native first-party Search service in draft PR #2 remains **local-index-only**. Newly added first-party adapter and aggregation modules have **not** been connected to its HTTP API or user interface, and no external provider is enabled, configured or queried. The standalone tests mock outbound transports.

The optional future Brave Search API adapter requires a legitimate API entitlement, server-side secret configuration, an explicit user choice and per-query sharing consent. A separately managed localhost SearXNG instance is an optional external service, not part of the GoreeCloud Search source tree; its upstream query forwarding must be disclosed. Neither third-party engine source nor legacy recovery code is imported.

Acceptance to activate an adapter requires integration into the server and UI, no-skip test suite and CI, secret and dependency review, query-privacy threat model, approved egress/billing limits, and real-browser accessibility checks. Remote listener, native OS packaging, real provider connectivity, and production deployment remain unapproved and unverified.
