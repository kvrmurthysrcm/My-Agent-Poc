from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OnlineLibraryMCPConfig:
    """Runtime settings for the Online Library MCP server."""

    api_base_url: str
    host: str
    port: int
    request_timeout_seconds: float


def load_config() -> OnlineLibraryMCPConfig:
    """Load MCP and upstream API settings from environment variables."""

    return OnlineLibraryMCPConfig(
        api_base_url=os.getenv("ONLINE_LIBRARY_API_BASE_URL", "http://127.0.0.1:8003").rstrip("/"),
        host=os.getenv("ONLINE_LIBRARY_MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("ONLINE_LIBRARY_MCP_PORT", "8004")),
        request_timeout_seconds=float(os.getenv("ONLINE_LIBRARY_MCP_TIMEOUT_SECONDS", "10")),
    )
