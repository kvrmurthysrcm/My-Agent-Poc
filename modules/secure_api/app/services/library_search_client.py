from typing import Any

import httpx

from app.config import Settings


class LibrarySearchServiceError(Exception):
    def __init__(
        self,
        *,
        status_code: int | None = None,
        error_type: str = "request_error",
        detail: Any = None,
    ) -> None:
        self.status_code = status_code
        self.error_type = error_type
        self.detail = detail
        super().__init__("Library search service failed")


class LibrarySearchClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.online_library_agent_base_url.rstrip("/")

    async def ask(self, payload: dict[str, Any]) -> Any:
        return await self._post_json("/ask", payload)

    async def health(self) -> dict[str, Any]:
        url = f"{self._base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.get(url, headers=self._api_key_header())
        except httpx.RequestError:
            return {"service": "online-library-search", "status": "unavailable", "url": url}

        if response.status_code >= 400:
            return {
                "service": "online-library-search",
                "status": "unhealthy",
                "status_code": response.status_code,
                "url": url,
            }

        return {
            "service": "online-library-search",
            "status": "available",
            "status_code": response.status_code,
            "url": url,
            "response": _response_body(response),
        }

    async def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=self._api_key_header())
        except httpx.TimeoutException as exc:
            raise LibrarySearchServiceError(error_type="timeout") from exc
        except httpx.RequestError as exc:
            raise LibrarySearchServiceError(error_type=type(exc).__name__) from exc

        if response.status_code >= 400:
            raise LibrarySearchServiceError(
                status_code=response.status_code,
                error_type="http_status_error",
                detail=response.text,
            )

        return _response_body(response)

    def _api_key_header(self) -> dict[str, str]:
        return {"X-API-Key": self._settings.downstream_api_key}


def _response_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type.lower():
        return response.json()
    return {"body": response.text}
