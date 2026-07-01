from typing import Any

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.keycloak_client import KeycloakAuthenticationError, KeycloakConflictError, KeycloakUnavailableError
from app.main import app
from app.routes.auth_routes import get_keycloak_admin_client, get_keycloak_client, get_registration_repository
from app.schemas import CurrentUser
from app.services.library_registration_repository import DuplicateLibraryUserError


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


class FakeKeycloakAdminClient:
    def __init__(self, *, conflict: bool = False) -> None:
        self.conflict = conflict
        self.deleted: list[str] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def create_registered_user(
        self,
        *,
        username: str,
        email: str,
        full_name: str,
        password: str,
        roles: list[str],
    ) -> str:
        self.calls.append(
            (
                "create_registered_user",
                {
                    "username": username,
                    "email": email,
                    "full_name": full_name,
                    "password": password,
                    "roles": roles,
                },
            )
        )
        if self.conflict:
            raise KeycloakConflictError("exists")
        return "kc-user-123"

    async def delete_user(self, *, user_id: str) -> None:
        self.deleted.append(user_id)


class FakeRegistrationRepository:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_subscription_tiers(self) -> list[dict[str, Any]]:
        return [{"tier_code": "FREE", "tier_name": "Free", "description": "Default free access tier"}]

    def create_approved_user_subscription(
        self,
        *,
        full_name: str,
        email: str,
        keycloak_user_id: str,
        tier_code: str,
    ) -> str:
        self.calls.append(
            (
                "create_approved_user_subscription",
                {
                    "full_name": full_name,
                    "email": email,
                    "keycloak_user_id": keycloak_user_id,
                    "tier_code": tier_code,
                },
            )
        )
        if self.duplicate:
            raise DuplicateLibraryUserError("exists")
        return "library-user-123"


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


def test_registration_options_returns_tiers_and_default_roles() -> None:
    repository = FakeRegistrationRepository()
    app.dependency_overrides[get_registration_repository] = lambda: repository
    client = TestClient(app)

    response = client.get("/auth/register/options")

    assert response.status_code == 200
    body = response.json()
    assert body["subscription_tiers"][0]["tier_code"] == "FREE"
    assert body["assigned_roles"] == ["rag_user", "rag_search_user"]
    assert body["role_assignment_mode"] == "automatic"


def test_register_creates_keycloak_and_library_user() -> None:
    keycloak_admin = FakeKeycloakAdminClient()
    repository = FakeRegistrationRepository()
    app.dependency_overrides[get_keycloak_admin_client] = lambda: keycloak_admin
    app.dependency_overrides[get_registration_repository] = lambda: repository
    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={
            "full_name": "New User",
            "email": "new@example.local",
            "username": "newuser",
            "password": "newpass123",
            "subscription_tier": "FREE",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["keycloak_user_id"] == "kc-user-123"
    assert body["library_user_id"] == "library-user-123"
    assert body["assigned_roles"] == ["rag_user", "rag_search_user"]
    assert keycloak_admin.calls[0][1]["roles"] == ["rag_user", "rag_search_user"]
    assert repository.calls[0][1]["keycloak_user_id"] == "kc-user-123"


def test_register_duplicate_keycloak_user_returns_409() -> None:
    app.dependency_overrides[get_keycloak_admin_client] = lambda: FakeKeycloakAdminClient(conflict=True)
    app.dependency_overrides[get_registration_repository] = lambda: FakeRegistrationRepository()
    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={
            "full_name": "New User",
            "email": "new@example.local",
            "username": "newuser",
            "password": "newpass123",
            "subscription_tier": "FREE",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "registration_user_exists"


def test_register_rolls_back_keycloak_user_when_library_duplicate() -> None:
    keycloak_admin = FakeKeycloakAdminClient()
    app.dependency_overrides[get_keycloak_admin_client] = lambda: keycloak_admin
    app.dependency_overrides[get_registration_repository] = lambda: FakeRegistrationRepository(duplicate=True)
    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={
            "full_name": "New User",
            "email": "new@example.local",
            "username": "newuser",
            "password": "newpass123",
            "subscription_tier": "FREE",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "library_user_exists"
    assert keycloak_admin.deleted == ["kc-user-123"]


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


def test_me_returns_current_user() -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        sub="user-123",
        preferred_username="raguser",
        email="raguser@example.local",
        name="RAG User",
        roles=["rag_user", "rag_search_user"],
        issuer="http://localhost:8080/realms/rag-auth-gateway",
    )
    client = TestClient(app)

    response = client.get("/auth/me", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json() == {
        "sub": "user-123",
        "preferred_username": "raguser",
        "email": "raguser@example.local",
        "name": "RAG User",
        "roles": ["rag_user", "rag_search_user"],
        "issuer": "http://localhost:8080/realms/rag-auth-gateway",
    }


def test_me_without_token_returns_401() -> None:
    client = TestClient(app)

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_bearer_token"


def test_me_with_invalid_token_returns_401() -> None:
    client = TestClient(app)

    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_bearer_token"
