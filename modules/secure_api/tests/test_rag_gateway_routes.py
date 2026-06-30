from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.main import app
from app.schemas import CurrentUser
from app.services.downstream_client import DownstreamClient


def _user(*roles: str) -> CurrentUser:
    return CurrentUser(
        sub="user-123",
        preferred_username="raguser",
        email="raguser@example.local",
        name="RAG User",
        roles=list(roles),
        issuer="http://localhost:8080/realms/rag-auth-gateway",
    )


def _client_for_user(user: CurrentUser) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("path", "role", "expected_url"),
    [
        ("/rag/search", "rag_search_user", "http://localhost:8001/rag/search"),
        ("/rag/answer", "rag_user", "http://localhost:8002/rag/answer"),
        ("/rag/ask", "rag_user", "http://localhost:8002/rag/answer"),
    ],
)
def test_json_rag_routes_call_expected_downstream_with_user_context_headers(
    path: str,
    role: str,
    expected_url: str,
) -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["json"] = request.content.decode()
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        client = _client_for_user(_user(role))
        response = client.post(
            path,
            json={"query": "test"},
            headers={"Authorization": "Bearer wrapper-token"},
        )
    finally:
        httpx.AsyncClient = original_async_client

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["url"] == expected_url
    assert captured["headers"]["x-api-key"] == "local-poc-internal-api-key"
    assert captured["headers"]["x-user-id"] == "user-123"
    assert captured["headers"]["x-username"] == "raguser"
    assert captured["headers"]["x-user-roles"] == role
    assert "authorization" not in captured["headers"]
    assert captured["json"] == '{"query":"test"}'


def test_rag_ingest_forwards_multipart_file_and_metadata() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.content
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = body.decode(errors="ignore")
        return httpx.Response(202, json={"resource_id": "res-1", "job_id": "job-1", "status": "QUEUED"})

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        client = _client_for_user(_user("rag_ingest_user"))
        response = client.post(
            "/rag/ingest",
            data={"metadata": '{"title":"Demo","indexing_mode":"STANDARD"}'},
            files={"file": ("demo.txt", b"hello world", "text/plain")},
            headers={"Authorization": "Bearer wrapper-token"},
        )
    finally:
        httpx.AsyncClient = original_async_client

    assert response.status_code == 200
    assert response.json() == {"resource_id": "res-1", "job_id": "job-1", "status": "QUEUED"}
    assert captured["url"] == "http://localhost:8000/rag/ingest"
    assert captured["headers"]["x-api-key"] == "local-poc-internal-api-key"
    assert captured["headers"]["x-user-id"] == "user-123"
    assert captured["headers"]["x-username"] == "raguser"
    assert captured["headers"]["x-user-roles"] == "rag_ingest_user"
    assert "authorization" not in captured["headers"]
    assert "multipart/form-data" in captured["headers"]["content-type"]
    assert 'name="metadata"' in captured["body"]
    assert '{"title":"Demo","indexing_mode":"STANDARD"}' in captured["body"]
    assert 'name="file"; filename="demo.txt"' in captured["body"]
    assert "hello world" in captured["body"]


def test_rag_search_allows_rag_user_role() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        client = _client_for_user(_user("rag_user"))
        response = client.post("/rag/search", json={"query": "allowed"})
    finally:
        httpx.AsyncClient = original_async_client

    assert response.status_code == 200


def test_rag_ingest_rejects_user_without_required_role() -> None:
    client = _client_for_user(_user("rag_user"))

    response = client.post(
        "/rag/ingest",
        data={"metadata": '{"title":"Demo"}'},
        files={"file": ("demo.txt", b"hello world", "text/plain")},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"


def test_downstream_error_maps_to_502_without_secret_details() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"secret": "do-not-return"})

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        client = _client_for_user(_user("rag_user"))
        response = client.post("/rag/answer", json={"query": "test"})
    finally:
        httpx.AsyncClient = original_async_client

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "downstream_request_failed"
    assert body["error"]["details"] == {
        "service": "rag-answer",
        "error_type": "http_status_error",
        "status_code": 500,
    }
    assert "do-not-return" not in response.text
    assert "local-poc-internal-api-key" not in response.text


def test_test_downstream_returns_each_service_status_without_failing_all() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "http://localhost:8001/health":
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(200, json={"status": "UP"})

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        client = _client_for_user(_user("rag_user"))
        response = client.get("/rag/test-downstream")
    finally:
        httpx.AsyncClient = original_async_client

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "OK"
    assert body["services"] == [
        {
            "service": "rag-ingest",
            "status": "available",
            "status_code": 200,
            "url": "http://localhost:8000/health",
            "response": {"status": "UP"},
        },
        {
            "service": "rag-search",
            "status": "unavailable",
            "url": "http://localhost:8001/health",
        },
        {
            "service": "rag-answer",
            "status": "available",
            "status_code": 200,
            "url": "http://localhost:8002/health",
            "response": {"status": "UP"},
        },
    ]


@pytest.mark.anyio
async def test_downstream_client_uses_custom_settings_and_does_not_forward_authorization() -> None:
    captured: dict[str, Any] = {}
    settings = Settings(
        DOWNSTREAM_API_KEY="test-api-key",
        RAG_SEARCH_BASE_URL="http://search.internal",
    )
    user = _user("rag_user", "rag_search_user")

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        response = await DownstreamClient(settings).post_json(
            service="rag-search",
            url=f"{settings.rag_search_base_url}/rag/search",
            payload={"query": "test"},
            user=user,
        )
    finally:
        httpx.AsyncClient = original_async_client

    assert response == {"ok": True}
    assert captured["url"] == "http://search.internal/rag/search"
    assert captured["headers"]["x-api-key"] == "test-api-key"
    assert captured["headers"]["x-user-roles"] == "rag_user,rag_search_user"
    assert "authorization" not in captured["headers"]
