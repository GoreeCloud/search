#!/usr/bin/env bash
# GoreeCloud Search private dev profile. Public exposure is deliberately unsupported here.
set -euo pipefail
SEARXNG_SECRET="${SEARXNG_SECRET:-}"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${#SEARXNG_SECRET}" -lt 32 ]]; then
  echo "GoreeCloud Search: SEARXNG_SECRET must be a nonempty unique 32+ character value." >&2
  exit 64
fi
if [[ "${SEARXNG_SECRET:-}" == *ultrasecretkey* ]]; then
  echo "GoreeCloud Search: upstream example secret refused." >&2
  exit 64
fi
if [[ "${SEARXNG_BIND_ADDRESS:-127.0.0.1}" != "127.0.0.1" ||
      "${SEARXNG_PUBLIC_INSTANCE:-false}" != "false" ||
      "${SEARXNG_METHOD:-POST}" != "POST" ||
      "${SEARXNG_IMAGE_PROXY:-true}" != "true" ]]; then
  echo "GoreeCloud Search: insecure or public-facing environment override refused." >&2
  exit 64
fi
export SEARXNG_BIND_ADDRESS="127.0.0.1"
export SEARXNG_DEBUG="false"
export GRANIAN_RELOAD="false"
export SEARXNG_PUBLIC_INSTANCE="false"
export SEARXNG_METHOD="POST"
export SEARXNG_IMAGE_PROXY="true"
export SEARXNG_SETTINGS_PATH="$ROOT/configs/goreecloud/settings.yml"
cd "$ROOT"
exec ./manage webapp.run "$@"
