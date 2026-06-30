from typing import Any

from fastapi import APIRouter, Depends
from starlette import status

from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.exceptions import AppError
from app.schemas import CurrentUser
from app.services.library_search_client import LibrarySearchClient, LibrarySearchServiceError

router = APIRouter(prefix="/library-search", tags=["library-search"])


def get_library_search_client(settings: Settings = Depends(get_settings)) -> LibrarySearchClient:
    return LibrarySearchClient(settings)


@router.post("/ask")
async def ask_library(
    payload: dict[str, Any],
    user: CurrentUser = Depends(get_current_user),
    client: LibrarySearchClient = Depends(get_library_search_client),
) -> Any:
    del user
    question = str(payload.get("question") or "").strip()
    if not question:
        raise AppError(
            "Question is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="invalid_library_search_request",
        )

    forwarded_payload = {
        "question": question,
        "limit": int(payload.get("limit") or 10),
        "offset": int(payload.get("offset") or 0),
        "include_raw": bool(payload.get("include_raw", True)),
    }
    try:
        return await client.ask(forwarded_payload)
    except LibrarySearchServiceError as exc:
        raise _library_search_app_error(exc) from exc


@router.get("/health")
async def library_search_health(
    user: CurrentUser = Depends(get_current_user),
    client: LibrarySearchClient = Depends(get_library_search_client),
) -> dict[str, Any]:
    del user
    return await client.health()


def _library_search_app_error(exc: LibrarySearchServiceError) -> AppError:
    details: dict[str, Any] = {"service": "online-library-search", "error_type": exc.error_type}
    if exc.status_code is not None:
        details["status_code"] = exc.status_code
    if exc.detail is not None:
        details["detail"] = exc.detail
    return AppError(
        "Library search service request failed.",
        status_code=status.HTTP_502_BAD_GATEWAY,
        error_code="library_search_request_failed",
        details=details,
    )
