"""Disposable OpenSearch index/create/search/delete integration acceptance.

Only executed with TEST_OPENSEARCH_URL against a throwaway single-node service.
"""
import os
from datetime import datetime, timezone

import pytest
from opensearchpy import OpenSearch

from goree_search.indexing import (
    INDEX_NAME, delete_document, document_id, ensure_index, index_document,
    search_documents,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_OPENSEARCH_URL"), reason="Requires disposable OpenSearch"
)


def test_index_query_delete_roundtrip():
    client = OpenSearch(
        hosts=[os.environ["TEST_OPENSEARCH_URL"]],
        max_retries=1, timeout=10
    )
    ensure_index(client)
    url = "https://search-fixture.example.org/article"
    document = {
        "url": url,
        "host": "search-fixture.example.org",
        "title": "Independent web retrieval",
        "description": "Crawlers and search results",
        "body": "GoreeCloud Search builds an independent public web index.",
        "language": "en",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": "a" * 64,
    }
    try:
        index_document(client, document)
        client.indices.refresh(index=INDEX_NAME)
        reply = search_documents(client, "Independent web retrieval", 10, 0)
        assert any(item["url"] == url for item in reply["results"])
        assert delete_document(client, url) is True
        assert not any(
            item["url"] == url
            for item in search_documents(client, "Independent web retrieval", 10, 0)["results"]
        )
        assert delete_document(client, url) is False
    finally:
        client.delete(index=INDEX_NAME, id=document_id(url), ignore=[404], refresh=True)
