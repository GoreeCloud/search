#!/usr/bin/env bash
# GoreeCloud Search image-only loopback development runner.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET="${SEARXNG_SECRET:-}"
if [[ "${#SECRET}" -lt 32 || "$SECRET" == *ultrasecretkey* ]]; then
  echo 'Supply a unique 32+ character SEARXNG_SECRET.' >&2
  exit 64
fi
if [[ "${SEARXNG_BIND_ADDRESS:-127.0.0.1}" != "127.0.0.1" ||
        "${SEARXNG_PUBLIC_INSTANCE:-false}" != "false" ||
        "${SEARXNG_METHOD:-POST}" != "POST" ]]; then
  echo 'Public and non-POST overrides are prohibited in private image QA.' >&2
  exit 64
fi
export SEARXNG_BIND_ADDRESS='127.0.0.1'
export SEARXNG_PUBLIC_INSTANCE='false'
export SEARXNG_METHOD='POST'
export SEARXNG_IMAGE_PROXY='true'
export SEARXNG_SETTINGS_PATH="$ROOT/configs/goreecloud/image-search-settings.yml"
cd "$ROOT"
exec ./manage webapp.run "$@"
