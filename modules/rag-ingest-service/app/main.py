from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.api.rag_ingest_routes import router as rag_router
from app.core.config import get_settings
from app.db import models  # noqa: F401
from app.db.session import Base, engine
from app.services.embedding_model_registry import validate_embedding_model

logger = logging.getLogger("rag_ingest_service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    run_startup_migrations(settings)
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


def should_run_startup_migrations(settings) -> bool:
    profile = settings.app_profile.strip().lower()
    if profile not in {"local", "dev", "development"}:
        return False
    if not settings.auto_migrate_on_startup:
        return False
    return True


def run_startup_migrations(settings) -> None:
    if not should_run_startup_migrations(settings):
        return

    service_root = Path(__file__).resolve().parents[1]
    alembic_ini = service_root / "alembic.ini"
    logger.info("Running local/dev Alembic migrations from %s", alembic_ini)
    alembic_config = AlembicConfig(str(alembic_ini))
    alembic_config.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_url)
    command.upgrade(alembic_config, "head")


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Ingestion Service", version="0.1.0", lifespan=lifespan)
    app.include_router(rag_router)

    @app.get("/", response_class=HTMLResponse)
    @app.get("/ui", response_class=HTMLResponse)
    def upload_ui() -> HTMLResponse:
        ui_path = Path(__file__).parent / "ui" / "index.html"
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "rag-ingest-service"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        settings = get_settings()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        validate_embedding_model(settings.embedding_provider, settings.embedding_model, settings.embedding_dimension)
        return {
            "status": "ready",
            "database": "ok",
            "embedding_provider": settings.embedding_provider.value,
            "embedding_model": settings.embedding_model,
        }

    return app


app = create_app()
