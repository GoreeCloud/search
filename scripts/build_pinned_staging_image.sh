#!/usr/bin/env bash
# Build a local, commit-pinned private Search candidate. Never pushes or deploys.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if (( $# != 1 )) || [[ ! "$1" =~ ^[a-f0-9]{40}$ ]]; then
  echo 'Usage: scripts/build_pinned_staging_image.sh <full-40-character-commit-sha>' >&2
  exit 64
fi
# A two-sided opt-in avoids a misleading "pinned" image when only one of the
# external upstream base images has an immutable reference. Defaults remain
# unchanged for existing Development workflows until real digests are vetted.
BUILDER_BASE_REF="${GC_SEARCH_BUILDER_BASE_REF:-docker.io/searxng/base:searxng-builder}"
RUNTIME_BASE_REF="${GC_SEARCH_RUNTIME_BASE_REF:-docker.io/searxng/base:searxng}"
BASE_MODE='MUTABLE_DEFAULTS_RELEASE_HOLD'
if [[ -v GC_SEARCH_BUILDER_BASE_REF || -v GC_SEARCH_RUNTIME_BASE_REF ]]; then
  if [[ ! "$BUILDER_BASE_REF" =~ ^docker\.io/searxng/base@sha256:[0-9a-f]{64}$ ]] ||
     [[ ! "$RUNTIME_BASE_REF" =~ ^docker\.io/searxng/base@sha256:[0-9a-f]{64}$ ]]; then
    echo 'Refusing image build: supply BOTH upstream base refs as docker.io/searxng/base@sha256:<64-lowercase-hex> (no tags).' >&2
    exit 64
  fi
  BASE_MODE='DIGEST_SYNTAX_ONLY_UNVERIFIED'
fi
EXPECTED_SHA="$1"
SOURCE_SHA="$(git rev-parse HEAD)"
if [[ "$SOURCE_SHA" != "$EXPECTED_SHA" ]]; then
  echo 'Refusing image build: checkout revision differs from approved SHA.' >&2
  exit 65
fi
if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  echo 'Refusing image build: checkout must be clean.' >&2
  exit 65
fi
SOURCE_REMOTE="$(git remote get-url origin)"
case "$SOURCE_REMOTE" in
  https://github.com/GoreeCloud/search|https://github.com/GoreeCloud/search.git|git@github.com:GoreeCloud/search.git)
    ;;
  *)
    echo 'Refusing image build: origin is not the authorized GoreeCloud/search repository.' >&2
    exit 65
    ;;
esac
for program in python3 docker git; do
  command -v "$program" >/dev/null || { echo "Missing required local build tool: $program" >&2; exit 69; }
done

# Generate the upstream-required file from the exact pinned checkout.
# This file is gitignored. Never silently reuse metadata from another revision.
python3 searx/version.py freeze
SHORT_SHA="$(git rev-parse --short HEAD)"
python3 - "$SOURCE_SHA" "$SHORT_SHA" <<'PY'
import ast
from pathlib import Path
import sys

full_sha, short_sha = sys.argv[1:]
frozen = Path("searx/version_frozen.py")
if not frozen.is_file():
    raise SystemExit("Refusing image build: required frozen version file is absent")
values = {}
for item in ast.parse(frozen.read_text(encoding="utf-8")).body:
    if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
        values[item.targets[0].id] = ast.literal_eval(item.value)
if values.get("GIT_URL") != "https://github.com/GoreeCloud/search":
    raise SystemExit("Refusing image build: version source identity mismatch")
if not str(values.get("VERSION_STRING", "")).endswith("+" + short_sha):
    raise SystemExit("Refusing image build: frozen version does not match pinned revision")
if not full_sha.startswith(short_sha):
    raise SystemExit("Refusing image build: invalid git short revision")
print("PINNED_FROZEN_VERSION_PASS")
PY

BUILDER_IMAGE="goreecloud/search-builder:staging-${SOURCE_SHA:0:12}"
IMAGE="goreecloud/search:staging-${SOURCE_SHA:0:12}"
docker build -f container/builder.dockerfile \
  --build-arg BUILDER_BASE_IMAGE="$BUILDER_BASE_REF" \
  -t "$BUILDER_IMAGE" .
docker build -f container/dist.dockerfile \
  --build-arg BUILDER_IMAGE="$BUILDER_IMAGE" \
  --build-arg RUNTIME_BASE_IMAGE="$RUNTIME_BASE_REF" \
  --build-arg VCS_REVISION="$SOURCE_SHA" \
  --build-arg VCS_URL="https://github.com/GoreeCloud/search" \
  --build-arg VERSION="dev-${SOURCE_SHA:0:12}" \
  --build-arg REQUESTED_BUILDER_BASE_REF="$BUILDER_BASE_REF" \
  --build-arg REQUESTED_RUNTIME_BASE_REF="$RUNTIME_BASE_REF" \
  -t "$IMAGE" .
IMAGE_REVISION="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$IMAGE")"
IMAGE_SOURCE="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.source"}}' "$IMAGE")"
IMAGE_REQUESTED_BUILDER_REF="$(docker image inspect --format '{{index .Config.Labels "org.goreecloud.search.requested-builder-base-ref"}}' "$IMAGE")"
IMAGE_REQUESTED_RUNTIME_REF="$(docker image inspect --format '{{index .Config.Labels "org.goreecloud.search.requested-runtime-base-ref"}}' "$IMAGE")"
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE")"
if [[ "$IMAGE_REVISION" != "$SOURCE_SHA" || "$IMAGE_SOURCE" != 'https://github.com/GoreeCloud/search' ||
      "$IMAGE_REQUESTED_BUILDER_REF" != "$BUILDER_BASE_REF" ||
      "$IMAGE_REQUESTED_RUNTIME_REF" != "$RUNTIME_BASE_REF" ]]; then
  echo 'Refusing candidate image: source or requested upstream base labels differ from build inputs.' >&2
  exit 66
fi
printf 'LOCAL_STAGING_IMAGE_PASS image=%s revision=%s image_id=%s\n' "$IMAGE" "$SOURCE_SHA" "$IMAGE_ID"
printf 'BASE_IMAGE_REFERENCE_MODE=%s builder=%s runtime=%s\n' "$BASE_MODE" "$BUILDER_BASE_REF" "$RUNTIME_BASE_REF"
echo 'No image was pushed or deployed. OCI labels are declared metadata, not cryptographic attestation.'
