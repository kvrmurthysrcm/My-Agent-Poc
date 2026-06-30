from typing import Any

import httpx
from fastapi import UploadFile

from app.config import Settings
from app.schemas import CurrentUser
from app.trace_context import outbound_trace_headers


class DownstreamServiceError(Exception):
    def __init__(
        self,
        *,
        service: str,
        status_code: int | None = None,
        error_type: str = "request_error",
    ) -> None:
        self.service = service
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(f"Downstream service failed: {service}")


class DownstreamClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def post_json(
        self,
        *,
        service: str,
        url: str,
        payload: dict[str, Any],
        user: CurrentUser,
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._user_context_headers(user),
                )
        except httpx.TimeoutException as exc:
            raise DownstreamServiceError(service=service, error_type="timeout") from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(service=service, error_type=type(exc).__name__) from exc

        if response.status_code >= 400:
            raise DownstreamServiceError(
                service=service,
                status_code=response.status_code,
                error_type="http_status_error",
            )

        return _response_body(response)

    async def get_json(
        self,
        *,
        service: str,
        url: str,
        user: CurrentUser,
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.get(
                    url,
                    headers=self._user_context_headers(user),
                )
        except httpx.TimeoutException as exc:
            raise DownstreamServiceError(service=service, error_type="timeout") from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(service=service, error_type=type(exc).__name__) from exc

        if response.status_code >= 400:
            raise DownstreamServiceError(
                service=service,
                status_code=response.status_code,
                error_type="http_status_error",
            )

        return _response_body(response)

    async def post_file(
        self,
        *,
        service: str,
        url: str,
        file: UploadFile,
        metadata: str,
        user: CurrentUser,
    ) -> Any:
        file_bytes = await file.read()
        files = {
            "file": (
                file.filename or "upload.bin",
                file_bytes,
                file.content_type or "application/octet-stream",
            )
        }
        data = {"metadata": metadata}

        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.post(
                    url,
                    data=data,
                    files=files,
                    headers=self._user_context_headers(user),
                )
        except httpx.TimeoutException as exc:
            raise DownstreamServiceError(service=service, error_type="timeout") from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(service=service, error_type=type(exc).__name__) from exc

        if response.status_code >= 400:
            raise DownstreamServiceError(
                service=service,
                status_code=response.status_code,
                error_type="http_status_error",
            )

        return _response_body(response)

    async def health(self, *, service: str, base_url: str) -> dict[str, Any]:
        health_url = f"{base_url.rstrip('/')}/health"
        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.get(health_url, headers=self._api_key_header())
        except httpx.RequestError:
            return {"service": service, "status": "unavailable", "url": health_url}

        if response.status_code >= 400:
            return {
                "service": service,
                "status": "unhealthy",
                "status_code": response.status_code,
                "url": health_url,
            }

        return {
            "service": service,
            "status": "available",
            "status_code": response.status_code,
            "url": health_url,
            "response": _response_body(response),
        }

    def _api_key_header(self) -> dict[str, str]:
        headers = {"X-API-Key": self._settings.downstream_api_key}
        headers.update(outbound_trace_headers())
        return headers

    def _user_context_headers(self, user: CurrentUser) -> dict[str, str]:
        headers = self._api_key_header()
        headers.update(
            {
                "X-User-Id": user.sub,
                "X-Username": user.preferred_username or "",
                "X-User-Roles": ",".join(user.roles),
            }
        )
        return headers


def _response_body(response: httpx.Response) -> Any:
    if not response.content:
        return None

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type.lower():
        return response.json()

    return {"body": response.text}
