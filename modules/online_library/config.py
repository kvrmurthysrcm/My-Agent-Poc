from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """Connection settings for the Online Library PostgreSQL database."""

    host: str
    port: int
    name: str
    user: str
    password: str


def load_database_config() -> DatabaseConfig:
    """Load DB settings from environment variables with local POC defaults."""

    return DatabaseConfig(
        host=os.getenv("ONLINE_LIBRARY_DB_HOST", "localhost"),
        port=int(os.getenv("ONLINE_LIBRARY_DB_PORT", "5432")),
        name=os.getenv("ONLINE_LIBRARY_DB_NAME", "online_library"),
        user=os.getenv("ONLINE_LIBRARY_DB_USER", "library_user"),
        password=os.getenv("ONLINE_LIBRARY_DB_PASSWORD", "library_pass"),
    )
