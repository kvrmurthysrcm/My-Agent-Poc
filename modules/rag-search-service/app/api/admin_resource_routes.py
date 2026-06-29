import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.admin_resources import (
    AdminDeleteResourceResult,
    AdminDeleteResourcesRequest,
    AdminDeleteResourcesResponse,
    AdminGraphRagSettingsRequest,
    AdminGraphRagSettingsResponse,
    AdminRetryResourceResponse,
    AdminResourceListResponse,
)
from app.services.admin_resource_service import AdminResourceService

router = APIRouter(prefix="/rag/admin", tags=["rag-admin"])


def require_admin_enabled(settings: Settings) -> None:
    if not settings.search_admin_enabled:
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/resources", response_model=AdminResourceListResponse)
def list_resources(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AdminResourceListResponse:
    require_admin_enabled(settings)
    resources = AdminResourceService(db).list_resources()
    return AdminResourceListResponse(total=len(resources), resources=resources)


@router.post("/resources/delete", response_model=AdminDeleteResourcesResponse)
def delete_resources(
    request: AdminDeleteResourcesRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AdminDeleteResourcesResponse:
    require_admin_enabled(settings)
    service = AdminResourceService(db)
    results: list[AdminDeleteResourceResult] = []

    for resource_id in request.resource_ids:
        try:
            deleted, counts, deleted_file_path = service.delete_resource(resource_id, force=request.force)
            db.commit()
            results.append(
                AdminDeleteResourceResult(
                    resource_id=resource_id,
                    deleted=deleted,
                    deleted_file_path=deleted_file_path,
                    deleted_counts=counts,
                    error=None if deleted else "Resource not found",
                )
            )
        except ValueError as exc:
            db.rollback()
            results.append(AdminDeleteResourceResult(resource_id=resource_id, deleted=False, error=str(exc)))
        except Exception as exc:
            db.rollback()
            results.append(AdminDeleteResourceResult(resource_id=resource_id, deleted=False, error=type(exc).__name__))

    return AdminDeleteResourcesResponse(
        requested=len(request.resource_ids),
        deleted=sum(1 for result in results if result.deleted),
        results=results,
    )


@router.post("/resources/{resource_id}/retry", response_model=AdminRetryResourceResponse, status_code=202)
def retry_resource(
    resource_id: str,
    settings: Settings = Depends(get_settings),
) -> AdminRetryResourceResponse:
    require_admin_enabled(settings)
    retry_url = f"{settings.rag_ingest_base_url.rstrip('/')}/rag/ingest/resources/{resource_id}/retry"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(retry_url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Unable to contact rag-ingest-service: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text}

    if response.status_code >= 400:
        detail = body.get("detail") if isinstance(body, dict) else str(body)
        raise HTTPException(status_code=response.status_code, detail=detail or "Retry request failed")

    return AdminRetryResourceResponse(
        resource_id=body.get("resource_id", resource_id),
        job_id=body.get("job_id"),
        status=body.get("status", "QUEUED"),
        indexing_mode=body.get("indexing_mode"),
        message=body.get("message", "Retry queued."),
    )


@router.get("/settings/graph-rag", response_model=AdminGraphRagSettingsResponse)
def get_graph_rag_settings(settings: Settings = Depends(get_settings)) -> AdminGraphRagSettingsResponse:
    require_admin_enabled(settings)
    body = _call_ingest_settings(settings, method="GET")
    return AdminGraphRagSettingsResponse(
        entity_batch_size=body["entity_batch_size"],
        relationship_batch_size=body["relationship_batch_size"],
        updated_at=body.get("updated_at"),
        message=body.get("message", "Graph RAG runtime settings loaded."),
    )


@router.put("/settings/graph-rag", response_model=AdminGraphRagSettingsResponse)
def update_graph_rag_settings(
    request: AdminGraphRagSettingsRequest,
    settings: Settings = Depends(get_settings),
) -> AdminGraphRagSettingsResponse:
    require_admin_enabled(settings)
    body = _call_ingest_settings(settings, method="PUT", json=request.model_dump())
    return AdminGraphRagSettingsResponse(
        entity_batch_size=body["entity_batch_size"],
        relationship_batch_size=body["relationship_batch_size"],
        updated_at=body.get("updated_at"),
        message=body.get("message", "Graph RAG runtime settings saved."),
    )


def _call_ingest_settings(settings: Settings, method: str, json: dict | None = None) -> dict:
    url = f"{settings.rag_ingest_base_url.rstrip('/')}/rag/settings/graph-rag"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.request(method, url, json=json)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Unable to contact rag-ingest-service: {exc}") from exc
    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text}
    if response.status_code >= 400:
        detail = body.get("detail") if isinstance(body, dict) else str(body)
        raise HTTPException(status_code=response.status_code, detail=detail or "Graph RAG settings request failed")
    return body
