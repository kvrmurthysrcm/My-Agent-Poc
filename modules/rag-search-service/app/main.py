from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.api.admin_resource_routes import router as admin_resource_router
from app.api.rag_search_routes import router as rag_search_router
from app.core.config import Settings, get_settings
from app.core.constants import EmbeddingProviderName
from app.db import models  # noqa: F401
from app.db.session import Base, engine
from app.services.embedding_model_registry import validate_embedding_model
from app.services.embedding_providers.ollama_dependency import OllamaDependencyError, check_ollama_available
from app.trace_context import install_log_record_factory, trace_context_middleware


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    settings = get_settings()
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    _log_ollama_startup_check(settings)
    yield


def _log_ollama_startup_check(settings: Settings) -> None:
    if settings.embedding_provider != EmbeddingProviderName.OLLAMA:
        return

    try:
        check_ollama_available(base_url=settings.ollama_base_url, model=settings.embedding_model)
    except OllamaDependencyError as exc:
        logger.error("Ollama embedding startup check failed: %s", exc)
    else:
        logger.info(
            "Ollama embedding startup check passed: provider=ollama model=%s base_url=%s",
            settings.embedding_model,
            settings.ollama_base_url,
        )


def create_app() -> FastAPI:
    install_log_record_factory()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s trace_id=%(trace_id)s span_id=%(span_id)s request_id=%(request_id)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    app = FastAPI(title="RAG Search Service", version="0.1.0", lifespan=lifespan)
    app.middleware("http")(trace_context_middleware)
    app.include_router(rag_search_router)
    app.include_router(admin_resource_router)

    @app.get("/", response_class=HTMLResponse)
    @app.get("/ui/search", response_class=HTMLResponse)
    def search_ui() -> HTMLResponse:
        ui_path = Path(__file__).parent / "ui" / "search.html"
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))

    @app.get("/ui/admin/resources", response_class=HTMLResponse)
    def admin_resources_ui() -> HTMLResponse:
        ui_path = Path(__file__).parent / "ui" / "admin_resources.html"
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "rag-search-service"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        settings = get_settings()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        validate_embedding_model(settings.embedding_provider, settings.embedding_model, settings.embedding_dimension)
        if settings.embedding_provider == EmbeddingProviderName.OLLAMA:
            try:
                check_ollama_available(base_url=settings.ollama_base_url, model=settings.embedding_model)
            except OllamaDependencyError as exc:
                raise HTTPException(status_code=503, detail=exc.to_public_detail()) from exc
        return {
            "status": "ready",
            "database": "ok",
            "embedding_provider": settings.embedding_provider.value,
            "embedding_model": settings.embedding_model,
        }

    return app


app = create_app()
