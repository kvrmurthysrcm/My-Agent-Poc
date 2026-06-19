from __future__ import annotations

from typing import Any

import httpx

from .config import OnlineLibraryMCPConfig, load_config


class OnlineLibraryAPIClient:
    """Small HTTP client for the existing Online Library FastAPI service."""

    def __init__(self, config: OnlineLibraryMCPConfig | None = None) -> None:
        self.config = config or load_config()

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call the upstream API and return a JSON object or a structured error."""

        url = f"{self.config.api_base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout_seconds) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            return {
                "error": "online_library_api_http_error",
                "status_code": exc.response.status_code,
                "url": str(exc.request.url),
                "detail": exc.response.text,
            }
        except httpx.RequestError as exc:
            return {
                "error": "online_library_api_request_error",
                "url": str(exc.request.url) if exc.request else url,
                "detail": str(exc),
            }
        except ValueError as exc:
            return {
                "error": "online_library_api_invalid_json",
                "url": url,
                "detail": str(exc),
            }

        if not isinstance(payload, dict):
            return {
                "error": "online_library_api_unexpected_payload",
                "url": url,
                "detail": "Expected a JSON object from the upstream API.",
                "payload": payload,
            }
        return payload
