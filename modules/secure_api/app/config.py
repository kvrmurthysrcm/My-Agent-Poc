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
    keycloak_timeout_seconds: float = Field(10.0, alias="KEYCLOAK_TIMEOUT_SECONDS")
    token_audience_validation_enabled: bool = Field(
        False,
        alias="TOKEN_AUDIENCE_VALIDATION_ENABLED",
    )
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
