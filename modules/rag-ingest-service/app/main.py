from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.api.rag_ingest_routes import router as rag_router
from app.core.constants import AsyncBackend
from app.core.config import get_settings
from app.db import models  # noqa: F401
from app.db.session import Base, SessionLocal, engine
from app.repositories.rag_job_repository import RagJobRepository
from app.repositories.runtime_settings_repository import RuntimeSettingsRepository
from app.services.embedding_model_registry import validate_embedding_model
from app.workers.rag_ingestion_worker import process_queued_jobs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    _ensure_runtime_settings_table()
    recovered = 0
    if settings.recover_processing_jobs_on_startup:
        recovered = _recover_processing_jobs_on_startup(settings.startup_recovery_stale_after_seconds)
    if settings.async_backend == AsyncBackend.FASTAPI_BACKGROUND_TASKS and (
        recovered or settings.process_queued_jobs_on_startup
    ):
        Thread(target=process_queued_jobs, daemon=True).start()
    yield


def _recover_processing_jobs_on_startup(stale_after_seconds: int) -> int:
    db = SessionLocal()
    try:
        recovered = RagJobRepository(db).recover_stale_processing_jobs(
            stale_after_seconds=stale_after_seconds,
            retry_delay_seconds=0,
        )
        db.commit()
        return recovered
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _ensure_runtime_settings_table() -> None:
    db = SessionLocal()
    try:
        RuntimeSettingsRepository(db).ensure_table()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
