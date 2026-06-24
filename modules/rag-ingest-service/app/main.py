from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "rag-ingest-service"}

    return app


app = create_app()
