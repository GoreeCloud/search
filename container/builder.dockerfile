# Preserve the existing Development default. A qualified release build must
# supply a separately verified immutable ref through --build-arg.
ARG BUILDER_BASE_IMAGE=docker.io/searxng/base:searxng-builder
FROM ${BUILDER_BASE_IMAGE} AS builder

COPY ./requirements.txt ./requirements-server.txt ./

ENV UV_NO_MANAGED_PYTHON="true"

RUN --mount=type=cache,id=uv,target=/root/.cache/uv set -eux -o pipefail; \
    uv venv; \
    uv pip install --requirements ./requirements.txt --requirements ./requirements-server.txt; \
    uv cache prune --ci; \
    find ./.venv/lib/ -type f -exec strip --strip-unneeded {} + || true; \
    find ./.venv/lib/ -type d -name "__pycache__" -exec rm -rf {} +; \
    find ./.venv/lib/ -type f -name "*.pyc" -delete; \
    python -m compileall -q -f -j 0 --invalidation-mode=unchecked-hash ./.venv/lib/

# The builder-specific .dockerignore excludes version_frozen.py from this
# context; the dist build uses the root .dockerignore to include its freshly
# generated, verified copy. Avoid COPY --exclude (not portable on CI Docker).
COPY ./searx/ ./searx/

RUN set -eux -o pipefail; \
    python -m compileall -q -f -j 0 --invalidation-mode=unchecked-hash ./searx/; \
    find ./searx/static/ -type f \
    \( -name "*.html" -o -name "*.css" -o -name "*.js" -o -name "*.svg" \) \
    -exec gzip -9 -k {} +; \
    find ./searx/static/ -type f \
    \( -name "*.html" -o -name "*.css" -o -name "*.js" -o -name "*.svg" \) \
    -exec brotli -9 -k {} +; \
    find ./searx/static/ -type f -name "*.gz" -exec gzip --test {} +; \
    find ./searx/static/ -type f -name "*.br" -exec brotli --test {} +
