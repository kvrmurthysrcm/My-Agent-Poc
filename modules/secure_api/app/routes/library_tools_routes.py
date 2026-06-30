from typing import Any

from fastapi import APIRouter, Depends
from starlette import status

from app.auth.dependencies import require_any_role
from app.auth.roles import RAG_ADMIN, SYSTEM_ADMIN
from app.config import Settings, get_settings
from app.exceptions import AppError
from app.schemas import CurrentUser
from app.services.library_tools_client import LibraryToolsClient, LibraryToolsServiceError

router = APIRouter(prefix="/library-tools", tags=["library-tools"])


def get_library_tools_client(settings: Settings = Depends(get_settings)) -> LibraryToolsClient:
    return LibraryToolsClient(settings)


@router.get("/tools")
async def list_tools(
    user: CurrentUser = Depends(require_any_role(RAG_ADMIN, SYSTEM_ADMIN)),
    client: LibraryToolsClient = Depends(get_library_tools_client),
) -> Any:
    del user
    try:
        return await client.list_tools()
    except LibraryToolsServiceError as exc:
        raise _library_tools_app_error(exc) from exc


@router.post("/call")
async def call_tool(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_ADMIN, SYSTEM_ADMIN)),
    client: LibraryToolsClient = Depends(get_library_tools_client),
) -> Any:
    del user
    name = str(payload.get("name") or "").strip()
    arguments = payload.get("arguments") or {}
    if not name:
        raise AppError("Tool name is required.", status_code=status.HTTP_400_BAD_REQUEST, error_code="invalid_tool_request")
    if not isinstance(arguments, dict):
        raise AppError(
            "Tool arguments must be a JSON object.",
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="invalid_tool_request",
        )
    try:
        return await client.call_tool(name, arguments)
    except LibraryToolsServiceError as exc:
        raise _library_tools_app_error(exc) from exc


@router.get("/health")
async def library_tools_health(
    user: CurrentUser = Depends(require_any_role(RAG_ADMIN, SYSTEM_ADMIN)),
    client: LibraryToolsClient = Depends(get_library_tools_client),
) -> dict[str, Any]:
    del user
    return await client.health()


def _library_tools_app_error(exc: LibraryToolsServiceError) -> AppError:
    details: dict[str, Any] = {"service": "online-library-tools", "error_type": exc.error_type}
    if exc.status_code is not None:
        details["status_code"] = exc.status_code
    if exc.detail is not None:
        details["detail"] = exc.detail
    return AppError(
        "Library tools service request failed.",
        status_code=status.HTTP_502_BAD_GATEWAY,
        error_code="library_tools_request_failed",
        details=details,
    )
