from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import UploadFile

from app.config import Settings
from app.schemas import CurrentUser
from app.trace_context import outbound_trace_headers


_SAFE_DEPENDENCY_ERROR_CODES = frozenset({"ollama_unavailable", "ollama_model_unavailable"})
_SAFE_DEPENDENCY_DETAIL_KEYS = frozenset({"dependency", "model"})


class DownstreamServiceError(Exception):
    def __init__(
        self,
        *,
        service: str,
        status_code: int | None = None,
        error_type: str = "request_error",
        public_error_code: str | None = None,
        public_message: str | None = None,
        public_details: dict[str, str] | None = None,
    ) -> None:
        self.service = service
        self.status_code = status_code
        self.error_type = error_type
        self.public_error_code = public_error_code
        self.public_message = public_message
        self.public_details = public_details or {}
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
        return await self._request_json(
            method="POST",
            service=service,
            url=url,
            payload=payload,
            user=user,
        )

    async def put_json(
        self,
        *,
        service: str,
        url: str,
        payload: dict[str, Any],
        user: CurrentUser,
    ) -> Any:
        """Forward an explicitly routed JSON update with gateway-only credentials."""

        return await self._request_json(
            method="PUT",
            service=service,
            url=url,
            payload=payload,
            user=user,
        )

    async def stream_post_json(
        self,
        *,
        service: str,
        url: str,
        payload: dict[str, Any],
        user: CurrentUser,
    ) -> tuple[AsyncIterator[bytes], str]:
        """Open an SSE response without forwarding the browser bearer token downstream.

        The caller owns the returned iterator.  Its ``finally`` block closes both
        the upstream response and HTTP client when the browser disconnects.
        """

        client = httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds)
        try:
            request = client.build_request(
                "POST",
                url,
                json=payload,
                headers=self._user_context_headers(user),
            )
            response = await client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            await client.aclose()
            raise DownstreamServiceError(service=service, error_type="timeout") from exc
        except httpx.RequestError as exc:
            await client.aclose()
            raise DownstreamServiceError(service=service, error_type=type(exc).__name__) from exc

        if response.status_code >= 400:
            status_code = response.status_code
            await response.aread()
            await response.aclose()
            await client.aclose()
            raise _downstream_http_status_error(service=service, response=response, status_code=status_code)

        async def stream() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_raw():
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        content_type = response.headers.get("content-type", "text/event-stream")
        return stream(), content_type

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
            raise _downstream_http_status_error(service=service, response=response)

        return _response_body(response)

    async def _request_json(
        self,
        *,
        method: str,
        service: str,
        url: str,
        payload: dict[str, Any],
        user: CurrentUser,
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self._settings.downstream_timeout_seconds) as client:
                response = await client.request(
                    method,
                    url,
                    json=payload,
                    headers=self._user_context_headers(user),
                )
        except httpx.TimeoutException as exc:
            raise DownstreamServiceError(service=service, error_type="timeout") from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(service=service, error_type=type(exc).__name__) from exc

        if response.status_code >= 400:
            raise _downstream_http_status_error(service=service, response=response)

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
            raise _downstream_http_status_error(service=service, response=response)

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


def _downstream_http_status_error(
    *,
    service: str,
    response: httpx.Response,
    status_code: int | None = None,
) -> DownstreamServiceError:
    public_error = _safe_dependency_error_from_response(response)
    return DownstreamServiceError(
        service=service,
        status_code=status_code or response.status_code,
        error_type="http_status_error",
        public_error_code=public_error["code"] if public_error else None,
        public_message=public_error["message"] if public_error else None,
        public_details=public_error["details"] if public_error else None,
    )


def _safe_dependency_error_from_response(response: httpx.Response) -> dict[str, Any] | None:
    """Forward only explicitly allowlisted, user-safe dependency failures.

    The gateway normally hides downstream response bodies.  Ollama availability is
    an actionable developer/user condition, so its controlled response is allowed
    through without exposing arbitrary downstream error text or credentials.
    """

    if response.status_code != 503:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    detail = payload.get("detail") if isinstance(payload, dict) else None
    if not isinstance(detail, dict):
        return None

    code = detail.get("code")
    message = detail.get("message")
    if code not in _SAFE_DEPENDENCY_ERROR_CODES or not isinstance(message, str) or not message.strip():
        return None

    raw_details = detail.get("details")
    safe_details = {
        key: value
        for key, value in (raw_details.items() if isinstance(raw_details, dict) else [])
        if key in _SAFE_DEPENDENCY_DETAIL_KEYS and isinstance(value, str)
    }
    return {"code": code, "message": message.strip()[:500], "details": safe_details}
