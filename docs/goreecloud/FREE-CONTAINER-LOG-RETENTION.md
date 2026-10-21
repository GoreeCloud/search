# Bounded Docker logs — no-cost free Search Development

**October 20, 2026 — source change only; live containers not recreated.**

Each free-first Search Compose project (canary, upgrade, working and
disposable staging) declares **Docker json-file** logging with:

- `max-size: "8m"`
- `max-file: "3"`

This retains compatibility with ordinary `docker logs` and bounds
**each future container's rotated JSON logs to roughly 24 MiB** under Docker's
rotation policy (roughly 48 MiB for a Search/ingress pair, excluding Docker
metadata, filesystem overhead and unrelated system logs). It is a
**storage/resource bound**, *not* a promise that access logs contain no query
parameters, search terms, client data or secrets. Existing request/URL
redaction and minimization rules remain mandatory. Do not increase log
verbosity, enable raw query/request logging, or export existing logs.

## Important live-state distinction

Editing `deploy/vps/compose.free-metasearch-working.yaml` **does not
change the log driver/options of currently running containers**.
Docker applies `HostConfig.LogConfig` at container creation. At the time
this source change was prepared, the live working Search and ingress containers
used `json-file` with no project-specific `max-size` or `max-file` set.
They were intentionally *not* recreated solely to enforce this setting,
because that would interrupt or replace a currently healthy NetBird-only
Development service without the separate cutover validation.

At the next governed, reversible new-canary rollout or container replacement,
validate the exact candidate source/image and do a full readback of the new
containers, including:

```bash
docker inspect --format '{{.HostConfig.LogConfig.Type}} {{json .HostConfig.LogConfig.Config}}' \
  goreecloud-search-free-working-search-1
docker inspect --format '{{.HostConfig.LogConfig.Type}} {{json .HostConfig.LogConfig.Config}}' \
  goreecloud-search-free-working-ingress-1
```

Both newly created services must report `json-file`,
`max-size:8m` and `max-file:3`. Keep the currently routed Caddy gateway
and previous healthy release as the fallback until the replacement passes
readiness, four-category free-source smoke, NetBird HTTPS and non-NetBird 403
checks. Do not remove rollback snapshots or silently deploy a new version
because a static Compose contract passed.

The four variants have offline unit/contract tests for exact settings,
no published Search/ingress ports, immutable root filesystem and security
capabilities. Docker Compose configuration is parsed without creating or
restarting containers. **Development-only, not Stable acceptance or
cryptographically signed container provenance.**
