from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "secure-api-gateway"
    app_version: str = "0.1.0"
    environment: Literal["local", "dev", "test", "stage", "prod"] = "local"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8010
    keycloak_url: str = Field("http://localhost:8080", alias="KEYCLOAK_URL")
    keycloak_realm: str = Field("rag-auth-gateway", alias="KEYCLOAK_REALM")
    keycloak_client_id: str = Field("fastapi-auth-gateway", alias="KEYCLOAK_CLIENT_ID")
    keycloak_client_secret: str = Field(
        "fastapi-auth-gateway-secret",
        alias="KEYCLOAK_CLIENT_SECRET",
    )
    keycloak_admin_client_id: str = Field("secure-gateway-admin", alias="KEYCLOAK_ADMIN_CLIENT_ID")
    keycloak_admin_client_secret: str = Field(
        "secure-gateway-admin-secret",
        alias="KEYCLOAK_ADMIN_CLIENT_SECRET",
    )
    keycloak_timeout_seconds: float = Field(10.0, alias="KEYCLOAK_TIMEOUT_SECONDS")
    default_registration_roles: list[str] = Field(
        default_factory=lambda: ["rag_user", "rag_search_user"],
        alias="DEFAULT_REGISTRATION_ROLES",
    )
    default_subscription_tier: str = Field("FREE", alias="DEFAULT_SUBSCRIPTION_TIER")
    online_library_db_host: str = Field("localhost", alias="ONLINE_LIBRARY_DB_HOST")
    online_library_db_port: int = Field(5432, alias="ONLINE_LIBRARY_DB_PORT")
    online_library_db_name: str = Field("online_library", alias="ONLINE_LIBRARY_DB_NAME")
    online_library_db_user: str = Field("library_user", alias="ONLINE_LIBRARY_DB_USER")
    online_library_db_password: str = Field("library_pass", alias="ONLINE_LIBRARY_DB_PASSWORD")
    token_audience_validation_enabled: bool = Field(
        False,
        alias="TOKEN_AUDIENCE_VALIDATION_ENABLED",
    )
    downstream_api_key: str = Field(
        "local-poc-internal-api-key",
        alias="DOWNSTREAM_API_KEY",
    )
    rag_ingest_base_url: str = Field("http://localhost:8000", alias="RAG_INGEST_BASE_URL")
    rag_search_base_url: str = Field("http://localhost:8001", alias="RAG_SEARCH_BASE_URL")
    rag_answer_base_url: str = Field("http://localhost:8002", alias="RAG_ANSWER_BASE_URL")
    online_library_agent_base_url: str = Field(
        "http://localhost:8005",
        alias="ONLINE_LIBRARY_AGENT_BASE_URL",
    )
    online_library_api_base_url: str = Field(
        "http://localhost:8003",
        alias="ONLINE_LIBRARY_API_BASE_URL",
    )
    online_library_mcp_url: str = Field("http://localhost:8004/mcp", alias="ONLINE_LIBRARY_MCP_URL")
    downstream_timeout_seconds: float = Field(600.0, alias="DOWNSTREAM_TIMEOUT_SECONDS")
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:4200",
            "http://localhost:8010",
        ]
    )

    @property
    def keycloak_token_url(self) -> str:
        base_url = self.keycloak_url.rstrip("/")
        return f"{base_url}/realms/{self.keycloak_realm}/protocol/openid-connect/token"

    @property
    def keycloak_admin_users_url(self) -> str:
        base_url = self.keycloak_url.rstrip("/")
        return f"{base_url}/admin/realms/{self.keycloak_realm}/users"

    @property
    def keycloak_admin_roles_url(self) -> str:
        base_url = self.keycloak_url.rstrip("/")
        return f"{base_url}/admin/realms/{self.keycloak_realm}/roles"

    @property
    def keycloak_logout_url(self) -> str:
        base_url = self.keycloak_url.rstrip("/")
        return f"{base_url}/realms/{self.keycloak_realm}/protocol/openid-connect/logout"

    @property
    def keycloak_issuer_url(self) -> str:
        base_url = self.keycloak_url.rstrip("/")
        return f"{base_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.keycloak_issuer_url}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
