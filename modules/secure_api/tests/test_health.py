from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_up() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_health_details_does_not_expose_secrets() -> None:
    response = client.get("/health/details")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UP"
    assert body["service"] == "secure-api-gateway"
    assert "secret" not in body
    assert "client_secret" not in body
    assert "api_key" not in body


def test_ui_returns_gateway_html() -> None:
    response = client.get("/ui")

    assert response.status_code == 200
    assert "Secure RAG Gateway" in response.text
    assert "loginForm" in response.text
    assert "compareForm" in response.text
    assert "themeButton" in response.text
