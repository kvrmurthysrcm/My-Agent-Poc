from typing import Any

import httpx

from app.config import Settings
from app.trace_context import outbound_trace_headers


class LibraryToolsServiceError(Exception):
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
        super().__init__("Library tools service failed")


class LibraryToolsClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._url = settings.online_library_mcp_url

    async def list_tools(self) -> Any:
        return await self._mcp_request("tools/list", {})

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self._mcp_request("tools/call", {"name": name, "arguments": arguments})

    async def health(self) -> dict[str, Any]:
        try:
            await self.list_tools()
        except LibraryToolsServiceError as exc:
            return {
                "service": "online-library-tools",
                "status": "unavailable",
                "url": self._url,
                "error_type": exc.error_type,
                "status_code": exc.status_code,
            }
        return {"service": "online-library-tools", "status": "available", "url": self._url}

    async def _mcp_request(self, method: str, params: dict[str, Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "X-API-Key": self._settings.downstream_api_key,
        }
        headers.update(outbound_trace_headers())
        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.post(self._url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise LibraryToolsServiceError(error_type="timeout") from exc
        except httpx.RequestError as exc:
            raise LibraryToolsServiceError(error_type=type(exc).__name__) from exc

        if response.status_code >= 400:
            raise LibraryToolsServiceError(
                status_code=response.status_code,
                error_type="http_status_error",
                detail=response.text,
            )

        body = _response_body(response)
        if isinstance(body, dict) and body.get("error"):
            raise LibraryToolsServiceError(error_type="mcp_error", detail=body["error"])
        return body.get("result") if isinstance(body, dict) and "result" in body else body


def _response_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type.lower():
        return response.json()
    return {"body": response.text}
