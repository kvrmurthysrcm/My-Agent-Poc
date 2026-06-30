from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.main import app
from app.schemas import CurrentUser


def _user() -> CurrentUser:
    return CurrentUser(
        sub="user-123",
        preferred_username="raguser",
        email="raguser@example.local",
        name="RAG User",
        roles=["rag_admin"],
        issuer="http://localhost:8080/realms/rag-auth-gateway",
    )


def teardown_function() -> None:
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_library_tools_list_forwards_json_rpc_and_api_key() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["json"] = request.content.decode()
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    app.dependency_overrides[get_current_user] = _user
    try:
        response = TestClient(app).get("/library-tools/tools", headers={"Authorization": "Bearer wrapper-token"})
    finally:
        httpx.AsyncClient = original_async_client

    assert response.status_code == 200
    assert response.json() == {"tools": []}
    assert captured["url"] == "http://localhost:8004/mcp"
    assert captured["headers"]["x-api-key"] == "local-poc-internal-api-key"
    assert "application/json" in captured["headers"]["content-type"]
    assert '"method":"tools/list"' in captured["json"]


def test_library_tools_call_validates_arguments_object() -> None:
    app.dependency_overrides[get_current_user] = _user

    response = TestClient(app).post(
        "/library-tools/call",
        json={"name": "get_resources", "arguments": ["bad"]},
        headers={"Authorization": "Bearer wrapper-token"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_tool_request"


def test_library_tools_rejects_non_admin_user() -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        sub="user-123",
        preferred_username="raguser",
        email="raguser@example.local",
        name="RAG User",
        roles=["rag_user"],
        issuer="http://localhost:8080/realms/rag-auth-gateway",
    )

    response = TestClient(app).get("/library-tools/tools", headers={"Authorization": "Bearer wrapper-token"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"
