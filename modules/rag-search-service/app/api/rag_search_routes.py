from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.search_request import SearchRequest
from app.schemas.search_response import SearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/rag", tags=["rag-search"])


@router.post("/search", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    try:
        return SearchService(db, settings).search(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search/debug", response_model=SearchResponse)
def debug_search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    if not settings.search_observability_enabled:
        raise HTTPException(
            status_code=404,
            detail="Search debug endpoint is disabled. Set SEARCH_OBSERVABILITY_ENABLED=true outside production.",
        )
    try:
        return SearchService(db, settings).debug_search(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
