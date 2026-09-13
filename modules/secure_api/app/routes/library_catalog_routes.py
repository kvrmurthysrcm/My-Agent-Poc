from typing import Any

from fastapi import APIRouter, Depends, Query
from starlette import status

from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.exceptions import AppError
from app.schemas import CurrentUser
from app.services.library_catalog_client import LibraryCatalogClient, LibraryCatalogServiceError

router = APIRouter(prefix="/library/catalog", tags=["library-catalog"])


def get_library_catalog_client(settings: Settings = Depends(get_settings)) -> LibraryCatalogClient:
    return LibraryCatalogClient(settings)


@router.get("/resources")
async def catalog_resources(
    q: str | None = Query(None),
    author: str | None = Query(None),
    category: str | None = Query(None),
    genre: str | None = Query(None),
    tag: str | None = Query(None),
    publisher: str | None = Query(None),
    language: str | None = Query(None),
    tier: str | None = Query(None),
    status_filter: str | None = Query("ACTIVE", alias="status"),
    published_from: str | None = Query(None),
    published_to: str | None = Query(None),
    sort: str = Query("title"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    client: LibraryCatalogClient = Depends(get_library_catalog_client),
) -> Any:
    del user
    try:
        return await client.search_resources(
            {
                "q": q,
                "author": author,
                "category": category,
                "genre": genre,
                "tag": tag,
                "publisher": publisher,
                "language": language,
                "tier": tier,
                "status": status_filter,
                "published_from": published_from,
                "published_to": published_to,
                "sort": sort,
                "limit": limit,
                "offset": offset,
            }
        )
    except LibraryCatalogServiceError as exc:
        raise _library_catalog_app_error(exc) from exc


@router.get("/resources/{resource_id}")
async def catalog_resource_detail(
    resource_id: str,
    user: CurrentUser = Depends(get_current_user),
    client: LibraryCatalogClient = Depends(get_library_catalog_client),
) -> Any:
    del user
    try:
        return await client.get_resource(resource_id)
    except LibraryCatalogServiceError as exc:
        raise _library_catalog_app_error(exc) from exc


@router.get("/facets")
async def catalog_facets(
    user: CurrentUser = Depends(get_current_user),
    client: LibraryCatalogClient = Depends(get_library_catalog_client),
) -> Any:
    del user
    try:
        return await client.facets()
    except LibraryCatalogServiceError as exc:
        raise _library_catalog_app_error(exc) from exc


@router.get("/health")
async def catalog_health(
    user: CurrentUser = Depends(get_current_user),
    client: LibraryCatalogClient = Depends(get_library_catalog_client),
) -> dict[str, Any]:
    del user
    return await client.health()


def _library_catalog_app_error(exc: LibraryCatalogServiceError) -> AppError:
    details: dict[str, Any] = {"service": "online-library-catalog", "error_type": exc.error_type}
    if exc.status_code is not None:
        details["status_code"] = exc.status_code
    if exc.detail is not None:
        details["detail"] = exc.detail
    return AppError(
        "Library catalog service request failed.",
        status_code=status.HTTP_502_BAD_GATEWAY,
        error_code="library_catalog_request_failed",
        details=details,
    )
