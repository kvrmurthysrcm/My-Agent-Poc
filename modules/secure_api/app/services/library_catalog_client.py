from typing import Any

import httpx

from app.config import Settings
from app.trace_context import outbound_trace_headers


class LibraryCatalogServiceError(Exception):
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
        super().__init__("Library catalog service failed")


class LibraryCatalogClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.online_library_api_base_url.rstrip("/")

    async def search_resources(self, params: dict[str, Any]) -> Any:
        return await self._get_json("/catalog/resources", params=params)

    async def get_resource(self, resource_id: str) -> Any:
        return await self._get_json(f"/catalog/resources/{resource_id}", params={})

    async def facets(self) -> Any:
        return await self._get_json("/catalog/facets", params={})

    async def health(self) -> dict[str, Any]:
        url = f"{self._base_url}/health/db"
        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.get(url, headers=self._api_key_header())
        except httpx.RequestError:
            return {"service": "online-library-catalog", "status": "unavailable", "url": url}
        if response.status_code >= 400:
            return {"service": "online-library-catalog", "status": "unhealthy", "status_code": response.status_code, "url": url}
        return {"service": "online-library-catalog", "status": "available", "status_code": response.status_code, "url": url, "response": _response_body(response)}

    async def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.get(url, params=_clean_params(params), headers=self._api_key_header())
        except httpx.TimeoutException as exc:
            raise LibraryCatalogServiceError(error_type="timeout") from exc
        except httpx.RequestError as exc:
            raise LibraryCatalogServiceError(error_type=type(exc).__name__) from exc
        if response.status_code >= 400:
            raise LibraryCatalogServiceError(status_code=response.status_code, error_type="http_status_error", detail=response.text)
        return _response_body(response)

    def _api_key_header(self) -> dict[str, str]:
        headers = {"X-API-Key": self._settings.downstream_api_key}
        headers.update(outbound_trace_headers())
        return headers


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None and value != ""}


def _response_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type.lower():
        return response.json()
    return {"body": response.text}
