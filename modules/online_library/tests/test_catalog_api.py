from fastapi.testclient import TestClient

from modules.online_library import api


def test_catalog_resources_forwards_filters(monkeypatch):
    captured = {}

    def fake_search_catalog_resources(**kwargs):
        captured.update(kwargs)
        return {"total": 1, "limit": kwargs["limit"], "offset": kwargs["offset"], "count": 1, "resources": []}

    monkeypatch.setattr(api, "search_catalog_resources", fake_search_catalog_resources)

    response = TestClient(api.app).get(
        "/catalog/resources",
        params={
            "q": "frankenstein",
            "author": "Mary Shelley",
            "genre": "Gothic",
            "tag": "classic",
            "tier": "FREE",
            "limit": 5,
            "offset": 10,
            "sort": "published_desc",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert captured["q"] == "frankenstein"
    assert captured["author"] == "Mary Shelley"
    assert captured["genre"] == "Gothic"
    assert captured["tag"] == "classic"
    assert captured["tier"] == "FREE"
    assert captured["limit"] == 5
    assert captured["offset"] == 10
    assert captured["sort"] == "published_desc"


def test_catalog_resource_detail_returns_resource(monkeypatch):
    monkeypatch.setattr(
        api,
        "get_catalog_resource_detail",
        lambda resource_id: {"resource_id": resource_id, "title": "Frankenstein", "authors": ["Mary Shelley"]},
    )

    response = TestClient(api.app).get("/catalog/resources/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 200
    assert response.json()["resource"]["title"] == "Frankenstein"


def test_catalog_resource_detail_returns_404(monkeypatch):
    monkeypatch.setattr(api, "get_catalog_resource_detail", lambda resource_id: None)

    response = TestClient(api.app).get("/catalog/resources/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Catalog resource not found."


def test_catalog_facets(monkeypatch):
    monkeypatch.setattr(
        api,
        "get_catalog_facets",
        lambda: {
            "categories": ["Fiction"],
            "genres": ["Fiction"],
            "authors": ["Mary Shelley"],
            "tags": ["classic"],
            "languages": ["English"],
            "subscription_tiers": [{"tier_code": "FREE", "tier_name": "Free"}],
        },
    )

    response = TestClient(api.app).get("/catalog/facets")

    assert response.status_code == 200
    assert response.json()["facets"]["authors"] == ["Mary Shelley"]
