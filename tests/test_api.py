from unittest.mock import patch

from fastapi.testclient import TestClient

from goree_search.api import app

client = TestClient(app)


def test_health_and_privacy_headers():
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_query_validation():
    assert client.get("/v1/search?q=x").status_code == 422
    assert client.get("/v1/search?q=valid&limit=40").status_code == 422


def test_empty_results_without_external_provider():
    with patch("goree_search.api.make_client") as make_client:
        with patch("goree_search.api.search_documents", return_value={
            "results": [], "total": 0, "offset": 0, "limit": 10
        }):
            res = client.get("/v1/search?q=public+web")
    assert res.status_code == 200
    assert res.json()["results"] == []
    make_client.assert_called_once()
