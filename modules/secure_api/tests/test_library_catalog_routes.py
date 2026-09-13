from typing import Any

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.main import app
from app.routes.library_catalog_routes import get_library_catalog_client
from app.schemas import CurrentUser


def _user(*roles: str) -> CurrentUser:
    return CurrentUser(
        sub="user-123",
        preferred_username="raguser",
        email="raguser@example.local",
        name="RAG User",
        roles=list(roles),
        issuer="http://localhost:8080/realms/rag-auth-gateway",
    )


class FakeLibraryCatalogClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def search_resources(self, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("search_resources", params))
        return {"total": 1, "limit": params["limit"], "offset": params["offset"], "count": 1, "resources": [{"title": "Frankenstein"}]}

    async def get_resource(self, resource_id: str) -> dict[str, Any]:
        self.calls.append(("get_resource", resource_id))
        return {"resource": {"resource_id": resource_id, "title": "Frankenstein"}}

    async def facets(self) -> dict[str, Any]:
        self.calls.append(("facets", None))
        return {"facets": {"authors": ["Mary Shelley"], "genres": ["Gothic"]}}

    async def health(self) -> dict[str, Any]:
        self.calls.append(("health", None))
        return {"service": "online-library-catalog", "status": "available"}


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_catalog_resources_allows_normal_user_and_forwards_params() -> None:
    fake = FakeLibraryCatalogClient()
    app.dependency_overrides[get_current_user] = lambda: _user("rag_user")
    app.dependency_overrides[get_library_catalog_client] = lambda: fake

    response = TestClient(app).get(
        "/library/catalog/resources",
        params={"q": "frankenstein", "author": "Mary", "genre": "Gothic", "limit": 5, "offset": 10},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["resources"][0]["title"] == "Frankenstein"
    assert fake.calls[0][0] == "search_resources"
    assert fake.calls[0][1]["q"] == "frankenstein"
    assert fake.calls[0][1]["author"] == "Mary"
    assert fake.calls[0][1]["genre"] == "Gothic"
    assert fake.calls[0][1]["limit"] == 5
    assert fake.calls[0][1]["offset"] == 10


def test_catalog_detail_allows_normal_user() -> None:
    fake = FakeLibraryCatalogClient()
    app.dependency_overrides[get_current_user] = lambda: _user("rag_user")
    app.dependency_overrides[get_library_catalog_client] = lambda: fake

    response = TestClient(app).get("/library/catalog/resources/resource-123", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["resource"]["resource_id"] == "resource-123"
    assert fake.calls == [("get_resource", "resource-123")]


def test_catalog_facets_allows_normal_user() -> None:
    fake = FakeLibraryCatalogClient()
    app.dependency_overrides[get_current_user] = lambda: _user("rag_user")
    app.dependency_overrides[get_library_catalog_client] = lambda: fake

    response = TestClient(app).get("/library/catalog/facets", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["facets"]["authors"] == ["Mary Shelley"]


def test_catalog_requires_authentication() -> None:
    response = TestClient(app).get("/library/catalog/resources")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_bearer_token"
