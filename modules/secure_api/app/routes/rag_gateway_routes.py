from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
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


@router.post("/graph/search")
async def graph_search(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_SEARCH_USER, RAG_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    """Securely expose the existing Graph RAG search operation."""

    return await _post_downstream(
        downstream_client=downstream_client,
        service="rag-search",
        url=f"{settings.rag_search_base_url.rstrip('/')}/rag/graph/search",
        payload=payload,
        user=user,
    )


@router.post("/search/combined")
async def combined_search(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_SEARCH_USER, RAG_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    """Securely expose combined standard and Graph RAG search."""

    return await _post_downstream(
        downstream_client=downstream_client,
        service="rag-search",
        url=f"{settings.rag_search_base_url.rstrip('/')}/rag/search/combined",
        payload=payload,
        user=user,
    )


@router.post("/search/debug")
async def debug_search(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_SEARCH_USER, RAG_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    """Securely expose debug search when the downstream service enables it."""

    return await _post_downstream(
        downstream_client=downstream_client,
        service="rag-search",
        url=f"{settings.rag_search_base_url.rstrip('/')}/rag/search/debug",
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


@router.post("/answer/compare/stream")
async def stream_compare_answers(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> StreamingResponse:
    """Proxy comparison SSE while keeping the internal API key server-side."""

    try:
        stream, content_type = await downstream_client.stream_post_json(
            service="rag-answer",
            url=f"{settings.rag_answer_base_url.rstrip('/')}/rag/answer/compare/stream",
            payload=payload,
            user=user,
        )
    except DownstreamServiceError as exc:
        raise _downstream_app_error(exc) from exc

    return StreamingResponse(
        stream,
        media_type=content_type.split(";", maxsplit=1)[0],
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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


@router.post("/resources/{resource_id}/index")
async def index_resource(
    resource_id: str,
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_ADMIN, SYSTEM_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    indexing_mode = str(payload.get("indexing_mode") or "").strip().upper()
    if indexing_mode not in {"STANDARD", "GRAPH", "BOTH"}:
        raise AppError(
            "indexing_mode must be STANDARD, GRAPH, or BOTH.",
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="invalid_indexing_mode",
        )
    try:
        return await downstream_client.post_json(
            service="rag-search",
            url=f"{settings.rag_search_base_url.rstrip('/')}/rag/admin/resources/{resource_id}/index",
            payload={"indexing_mode": indexing_mode},
            user=user,
        )
    except DownstreamServiceError as exc:
        raise _downstream_app_error(exc) from exc


@router.get("/ingest/jobs/{job_id}")
async def ingestion_job(
    job_id: str,
    user: CurrentUser = Depends(require_any_role(RAG_INGEST_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    """Retrieve an ingestion job through the gateway authorization boundary."""

    try:
        return await downstream_client.get_json(
            service="rag-ingest",
            url=f"{settings.rag_ingest_base_url.rstrip('/')}/rag/ingest/jobs/{job_id}",
            user=user,
        )
    except DownstreamServiceError as exc:
        raise _downstream_app_error(exc) from exc


@router.get("/ingest/jobs/{job_id}/errors")
async def ingestion_job_errors(
    job_id: str,
    user: CurrentUser = Depends(require_any_role(RAG_INGEST_USER, RAG_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    """Retrieve ingestion errors through the gateway authorization boundary."""

    try:
        return await downstream_client.get_json(
            service="rag-ingest",
            url=f"{settings.rag_ingest_base_url.rstrip('/')}/rag/ingest/jobs/{job_id}/errors",
            user=user,
        )
    except DownstreamServiceError as exc:
        raise _downstream_app_error(exc) from exc


@router.get("/admin/settings/graph-rag")
async def graph_rag_settings(
    user: CurrentUser = Depends(require_any_role(RAG_ADMIN, SYSTEM_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    """Read Graph RAG runtime settings through the existing admin service."""

    try:
        return await downstream_client.get_json(
            service="rag-search",
            url=f"{settings.rag_search_base_url.rstrip('/')}/rag/admin/settings/graph-rag",
            user=user,
        )
    except DownstreamServiceError as exc:
        raise _downstream_app_error(exc) from exc


@router.put("/admin/settings/graph-rag")
async def update_graph_rag_settings(
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_any_role(RAG_ADMIN, SYSTEM_ADMIN)),
    settings: Settings = Depends(get_settings),
    downstream_client: DownstreamClient = Depends(get_downstream_client),
) -> Any:
    """Update Graph RAG runtime settings through the existing admin service."""

    try:
        return await downstream_client.put_json(
            service="rag-search",
            url=f"{settings.rag_search_base_url.rstrip('/')}/rag/admin/settings/graph-rag",
            payload=payload,
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
    if exc.public_error_code and exc.public_message:
        details.update(exc.public_details)
        return AppError(
            exc.public_message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=exc.public_error_code,
            details=details,
        )
    return AppError(
        "Downstream service request failed.",
        status_code=status.HTTP_502_BAD_GATEWAY,
        error_code="downstream_request_failed",
        details=details,
    )
