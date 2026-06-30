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
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:4200",
            "http://localhost:8010",
        ]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
