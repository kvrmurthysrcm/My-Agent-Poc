from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.admin_resources import (
    AdminDeleteResourceResult,
    AdminDeleteResourcesRequest,
    AdminDeleteResourcesResponse,
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
