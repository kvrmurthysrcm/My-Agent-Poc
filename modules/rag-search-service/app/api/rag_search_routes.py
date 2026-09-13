import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.graph_search import CombinedSearchResponse, GraphSearchRequest, GraphSearchResponse
from app.schemas.search_request import SearchRequest
from app.schemas.search_response import SearchResponse
from app.services.graph_search_service import GraphSearchService
from app.services.embedding_providers.ollama_dependency import OllamaDependencyError
from app.services.search_service import SearchService

router = APIRouter(prefix="/rag", tags=["rag-search"])
logger = logging.getLogger(__name__)


@router.post("/search", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    try:
        return SearchService(db, settings).search(request)
    except OllamaDependencyError as exc:
        logger.error("Search request dependency unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=exc.to_public_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/graph/search", response_model=GraphSearchResponse)
def graph_search(
    request: GraphSearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GraphSearchResponse:
    try:
        return GraphSearchService(db, settings).search(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search/combined", response_model=CombinedSearchResponse)
def combined_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CombinedSearchResponse:
    try:
        standard_results = SearchService(db, settings).search(request)
        resource_id = request.filters.resource_id if request.filters else None
        graph_results = GraphSearchService(db, settings).search(
            GraphSearchRequest(
                query=request.query,
                resource_ids=[resource_id] if resource_id else [],
                top_k=request.top_k or settings.search_default_top_k,
            )
        )
        return CombinedSearchResponse(standard_results=standard_results, graph_results=graph_results)
    except OllamaDependencyError as exc:
        logger.error("Combined search dependency unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=exc.to_public_detail()) from exc
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
    except OllamaDependencyError as exc:
        logger.error("Search debug request dependency unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=exc.to_public_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
