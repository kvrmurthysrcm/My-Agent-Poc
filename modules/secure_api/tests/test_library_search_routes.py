from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.main import app
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


def teardown_function() -> None:
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_library_search_allows_normal_user_and_forwards_api_key() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["json"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "question": "Show me books written by Kelly",
                "selected_tool": "get_resources",
                "tool_arguments": {"limit": 5, "offset": 0},
                "answer": "Found matching resources.",
                "debug": {},
                "raw_tool_result": {"rows": []},
            },
        )

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    app.dependency_overrides[get_current_user] = lambda: _user("rag_user")
    try:
        response = TestClient(app).post(
            "/library-search/ask",
            json={"question": "Show me books written by Kelly", "limit": 5, "offset": 0},
            headers={"Authorization": "Bearer wrapper-token"},
        )
    finally:
        httpx.AsyncClient = original_async_client

    assert response.status_code == 200
    assert response.json()["selected_tool"] == "get_resources"
    assert captured["url"] == "http://localhost:8005/ask"
    assert captured["headers"]["x-api-key"] == "local-poc-internal-api-key"
    assert '"question":"Show me books written by Kelly"' in captured["json"]


def test_library_search_rejects_blank_question() -> None:
    app.dependency_overrides[get_current_user] = lambda: _user("rag_user")

    response = TestClient(app).post(
        "/library-search/ask",
        json={"question": " "},
        headers={"Authorization": "Bearer wrapper-token"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_library_search_request"
