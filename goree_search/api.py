"""Public read-only HTTP API. No accounts, tracking identifiers or raw query logs."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, Response
from opensearchpy.exceptions import OpenSearchException

from .indexing import make_client, search_documents

app = FastAPI(
    title="GoreeCloud Search API", version="0.1.0-alpha",
    docs_url=None, redoc_url=None,
)


@app.middleware("http")
async def privacy_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/v1/health")
def health():
    return {"status": "ok"}


@app.get("/v1/search")
def search(
    response: Response,
    q: str = Query(min_length=2, max_length=256),
    limit: int = Query(default=10, ge=1, le=30),
    offset: int = Query(default=0, ge=0, le=1000),
):
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Query must contain at least two characters")
    try:
        return search_documents(make_client(), query, limit, offset)
    except (OpenSearchException, ConnectionError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Search index unavailable") from exc
