from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.rag_ingest_routes import router as rag_router
from app.db import models  # noqa: F401
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


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

    return app


app = create_app()
