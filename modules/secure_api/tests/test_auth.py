from typing import Any

from fastapi.testclient import TestClient

from app.auth.keycloak_client import KeycloakAuthenticationError, KeycloakUnavailableError
from app.main import app
from app.routes.auth_routes import get_keycloak_client


class FakeKeycloakClient:
    def __init__(
        self,
        *,
        token_data: dict[str, Any] | None = None,
        auth_error: bool = False,
        unavailable: bool = False,
    ) -> None:
        self.token_data = token_data or {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "Bearer",
            "expires_in": 300,
            "refresh_expires_in": 1800,
            "scope": "openid profile email",
        }
        self.auth_error = auth_error
        self.unavailable = unavailable
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def password_grant(self, *, username: str, password: str) -> dict[str, Any]:
        self.calls.append(("password_grant", {"username": username, "password": password}))
        return self._token_or_raise()

    async def refresh(self, *, refresh_token: str) -> dict[str, Any]:
        self.calls.append(("refresh", {"refresh_token": refresh_token}))
        return self._token_or_raise()

    async def logout(self, *, refresh_token: str) -> None:
        self.calls.append(("logout", {"refresh_token": refresh_token}))
        self._raise_if_needed()

    def _token_or_raise(self) -> dict[str, Any]:
        self._raise_if_needed()
        return self.token_data

    def _raise_if_needed(self) -> None:
        if self.unavailable:
            raise KeycloakUnavailableError("unavailable")
        if self.auth_error:
            raise KeycloakAuthenticationError("invalid")


def client_with_keycloak(fake_client: FakeKeycloakClient) -> TestClient:
    app.dependency_overrides[get_keycloak_client] = lambda: fake_client
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_login_returns_access_token() -> None:
    fake_client = FakeKeycloakClient()
    client = client_with_keycloak(fake_client)

    response = client.post("/auth/login", json={"username": "raguser", "password": "raguser123"})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "access-token"
    assert body["refresh_token"] == "refresh-token"
    assert fake_client.calls == [("password_grant", {"username": "raguser", "password": "raguser123"})]


def test_login_with_wrong_password_returns_401() -> None:
    client = client_with_keycloak(FakeKeycloakClient(auth_error=True))

    response = client.post("/auth/login", json={"username": "raguser", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_when_keycloak_unavailable_returns_503() -> None:
    client = client_with_keycloak(FakeKeycloakClient(unavailable=True))

    response = client.post("/auth/login", json={"username": "raguser", "password": "raguser123"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "keycloak_unavailable"


def test_refresh_returns_new_access_token() -> None:
    fake_client = FakeKeycloakClient(token_data={"access_token": "new-access", "token_type": "Bearer"})
    client = client_with_keycloak(fake_client)

    response = client.post("/auth/refresh", json={"refresh_token": "refresh-token"})

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access"
    assert fake_client.calls == [("refresh", {"refresh_token": "refresh-token"})]


def test_logout_returns_logged_out() -> None:
    fake_client = FakeKeycloakClient()
    client = client_with_keycloak(fake_client)

    response = client.post("/auth/logout", json={"refresh_token": "refresh-token"})

    assert response.status_code == 200
    assert response.json() == {"status": "LOGGED_OUT"}
    assert fake_client.calls == [("logout", {"refresh_token": "refresh-token"})]
