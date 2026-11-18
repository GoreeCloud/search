from unittest.mock import MagicMock

from goree_search.indexing import document_id, search_documents


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
