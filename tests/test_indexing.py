from unittest.mock import MagicMock

from goree_search.indexing import delete_document, document_id, search_documents


def test_stable_id():
    assert document_id("https://example.org/a#fragment") == document_id("https://example.org/a")
    assert len(document_id("https://example.org/a")) == 64


def test_rank_query_and_result_projection():
    client = MagicMock()
    client.search.return_value = {"hits": {"total": {"value": 1}, "hits": [
        {"_score": 2.5, "_source": {
            "url": "https://example.org/", "title": "Title", "body": "Body"
        }}
    ]}}
    result = search_documents(client, "goree cloud", 10, 0)
    assert result["total"] == 1
    assert result["results"][0]["title"] == "Title"
    body = client.search.call_args.kwargs["body"]
    assert body["query"]["multi_match"]["query"] == "goree cloud"


def test_delete_idempotent_response():
    client = MagicMock()
    client.delete.return_value = {"result": "deleted"}
    assert delete_document(client, "https://example.org/") is True
    client.delete.assert_called_once_with(
        index="goree-web-v1",
        id=document_id("https://example.org/"),
        refresh="wait_for",
    )
    client.delete.return_value = {"result": "not_found"}
    assert delete_document(client, "https://example.org/") is False
