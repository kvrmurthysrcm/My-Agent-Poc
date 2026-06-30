from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from starlette import status

from app.auth.dependencies import get_current_user, require_any_role
from app.auth.roles import RAG_ADMIN, RAG_INGEST_USER, RAG_SEARCH_USER, RAG_USER, SYSTEM_ADMIN
from app.config import Settings, get_settings
from app.exceptions import AppError
from app.schemas import CurrentUser
from app.services.downstream_client import DownstreamClient, DownstreamServiceError

router = APIRouter(prefix="/rag", tags=["rag-gateway"])


def get_downstream_client(settings: Settings = Depends(get_settings)) -> DownstreamClient:
    return DownstreamClient(settings)


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    user: CurrentUser = Depends(require_any_role(RAG_INGEST_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    try:
        return await downstream_client.post_file(
            service="rag-ingest",
            url=f"{settings.rag_ingest_base_url.rstrip('/')}/rag/ingest",
            file=file,
            metadata=metadata,
            user=user,
        )
    except DownstreamServiceError as exc:
        raise _downstream_app_error(exc) from exc


@router.post("/search")
async def search(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_SEARCH_USER, RAG_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    return await _post_downstream(
        downstream_client=downstream_client,
        service="rag-search",
        url=f"{settings.rag_search_base_url.rstrip('/')}/rag/search",
        payload=payload,
        user=user,
    )


@router.post("/answer")
async def answer(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    return await _post_downstream(
        downstream_client=downstream_client,
        service="rag-answer",
        url=f"{settings.rag_answer_base_url.rstrip('/')}/rag/answer",
        payload=payload,
        user=user,
    )


@router.post("/answer/compare")
async def compare_answers(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    return await _post_downstream(
        downstream_client=downstream_client,
        service="rag-answer",
        url=f"{settings.rag_answer_base_url.rstrip('/')}/rag/answer/compare",
        payload=payload,
        user=user,
    )


@router.post("/ask")
async def ask(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    return await answer(
        payload=payload,
        user=user,
        settings=settings,
        downstream_client=downstream_client,
    )


@router.get("/test-downstream")
async def test_downstream(
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> dict[str, Any]:
    del user
    return {
        "status": "OK",
        "services": [
            await downstream_client.health(service="rag-ingest", base_url=settings.rag_ingest_base_url),
            await downstream_client.health(service="rag-search", base_url=settings.rag_search_base_url),
            await downstream_client.health(service="rag-answer", base_url=settings.rag_answer_base_url),
        ],
    }


@router.get("/resources")
async def list_resources(
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    try:
        return await downstream_client.get_json(
            service="rag-search",
            url=f"{settings.rag_search_base_url.rstrip('/')}/rag/admin/resources",
            user=user,
        )
    except DownstreamServiceError as exc:
        raise _downstream_app_error(exc) from exc


@router.post("/resources/delete")
async def delete_resources(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_ADMIN, SYSTEM_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    return await _post_downstream(
        downstream_client=downstream_client,
        service="rag-search",
        url=f"{settings.rag_search_base_url.rstrip('/')}/rag/admin/resources/delete",
        payload=payload,
        user=user,
    )


@router.post("/resources/{resource_id}/retry")
async def retry_resource(
    resource_id: str,
    user: CurrentUser = Depends(require_any_role(RAG_ADMIN, SYSTEM_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    try:
        return await downstream_client.post_json(
            service="rag-search",
            url=f"{settings.rag_search_base_url.rstrip('/')}/rag/admin/resources/{resource_id}/retry",
            payload={},
            user=user,
        )
    except DownstreamServiceError as exc:
        raise _downstream_app_error(exc) from exc


async def _post_downstream(
    *,
    downstream_client: DownstreamClient,
    service: str,
    url: str,
    payload: dict[str, Any],
    user: CurrentUser,
) -> Any:
    try:
        return await downstream_client.post_json(
            service=service,
            url=url,
            payload=payload,
            user=user,
        )
    except DownstreamServiceError as exc:
        raise _downstream_app_error(exc) from exc


def _downstream_app_error(exc: DownstreamServiceError) -> AppError:
    details: dict[str, Any] = {"service": exc.service, "error_type": exc.error_type}
    if exc.status_code is not None:
        details["status_code"] = exc.status_code
    return AppError(
        "Downstream service request failed.",
        status_code=status.HTTP_502_BAD_GATEWAY,
        error_code="downstream_request_failed",
        details=details,
    )
