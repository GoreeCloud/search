"""OpenSearch mappings, idempotent ingestion, document deletion and retrieval."""
from __future__ import annotations

import hashlib
import os
from typing import Any

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError

from .security import normalize_url

INDEX_NAME = os.environ.get("SEARCH_INDEX", "goree-web-v1")
INDEX_MAPPING = {
    "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "url": {"type": "keyword", "ignore_above": 2048},
            "host": {"type": "keyword"},
            "title": {"type": "text"},
            "description": {"type": "text"},
            "body": {"type": "text"},
            "language": {"type": "keyword"},
            "fetched_at": {"type": "date"},
            "content_hash": {"type": "keyword"},
        },
    },
}


def make_client() -> OpenSearch:
    endpoint = os.environ.get("OPENSEARCH_URL", "http://127.0.0.1:9200")
    if not endpoint.startswith(("https://", "http://")):
        raise RuntimeError("OPENSEARCH_URL must be HTTP(S)")
    return OpenSearch(hosts=[endpoint], timeout=10, max_retries=1, retry_on_timeout=False)


def ensure_index(client: OpenSearch) -> None:
    if not client.indices.exists(index=INDEX_NAME):
        # Never silently ignore mapping errors during initialization.
        client.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)


def document_id(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def index_document(client: OpenSearch, document: dict[str, Any]) -> None:
    doc = {name: document[name] for name in INDEX_MAPPING["mappings"]["properties"]}
    client.index(index=INDEX_NAME, id=document_id(document["url"]), body=doc, refresh=False)


def delete_document(client: OpenSearch, url: str) -> bool:
    """Remove indexed URL and wait for a search-visible refresh. Safe to repeat."""
    try:
        result = client.delete(index=INDEX_NAME, id=document_id(url), refresh="wait_for")
    except NotFoundError:
        return False
    return result.get("result") != "not_found"


def search_documents(client: OpenSearch, query: str, limit: int, offset: int) -> dict[str, Any]:
    body = {
        "from": offset,
        "size": limit,
        "track_total_hits": True,
        "_source": ["url", "host", "title", "description", "body", "fetched_at"],
        "query": {"multi_match": {
            "query": query,
            "fields": ["title^4", "description^2", "body"],
            "type": "best_fields",
        }},
    }
    response = client.search(index=INDEX_NAME, body=body)
    hits = response.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    results = []
    for item in hits.get("hits", []):
        src = item.get("_source", {})
        try:
            safe_url = normalize_url(src["url"])
        except (KeyError, ValueError):
            continue
        results.append({
            "url": safe_url,
            "title": str(src.get("title") or safe_url)[:240],
            "description": str(src.get("description") or src.get("body") or "")[:300],
            "host": src.get("host", ""),
            "score": item.get("_score", 0),
        })
    return {"total": total, "limit": limit, "offset": offset, "results": results}
