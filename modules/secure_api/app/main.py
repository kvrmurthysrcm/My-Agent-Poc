from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.exceptions import register_exception_handlers
from app.logging_config import configure_logging
from app.middleware.request_context import request_context_middleware
from app.routes.auth_routes import router as auth_router
from app.routes.health_routes import router as health_router
from app.routes.library_search_routes import router as library_search_router
from app.routes.library_tools_routes import router as library_tools_router
from app.routes.rag_gateway_routes import router as rag_gateway_router
from app.routes.ui_routes import router as ui_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Secure API Gateway base scaffold.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_context_middleware)

    register_exception_handlers(app)
    app.include_router(ui_router)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(rag_gateway_router)
    app.include_router(library_search_router)
    app.include_router(library_tools_router)

    return app


app = create_app()
