import logging
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.rag_answer_routes import router as answer_router
from app.core.config import get_settings
from app.services.llm_providers.factory import LlmProviderFactory
from app.services.search_client import RagSearchClient
from app.trace_context import install_log_record_factory, trace_context_middleware


def create_app() -> FastAPI:
    install_log_record_factory()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s trace_id=%(trace_id)s span_id=%(span_id)s request_id=%(request_id)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    app = FastAPI(title="RAG Answer Service", version="0.1.0")
    app.middleware("http")(trace_context_middleware)
    app.include_router(answer_router)

    @app.get("/", response_class=HTMLResponse)
    @app.get("/ui/answer", response_class=HTMLResponse)
    def answer_ui() -> HTMLResponse:
        ui_path = Path(__file__).parent / "ui" / "answer.html"
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "rag-answer-service"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        settings = get_settings()
        search_health = RagSearchClient(settings).health()
        provider = LlmProviderFactory.build(settings)
        return {
            "status": "ready",
            "search_service": search_health.get("status", "unknown"),
            "llm_provider": provider.provider_name,
            "llm_model": provider.model,
        }

    return app


app = create_app()
