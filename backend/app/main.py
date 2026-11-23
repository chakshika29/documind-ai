import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.chat import router as chat_router
from app.api.knowledge import router as knowledge_router
from app.api.routes import router
from app.core.config import Settings
from app.core.errors import KnowledgeError
from app.db.database import create_database
from app.models.library import Base
from app.rag.llm import LocalLLM
from app.services.chat import ChatService
from app.services.knowledge import KnowledgeBase

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_database(config.database_path)
        llm = LocalLLM(config)
        try:
            Base.metadata.create_all(engine)
            app.state.engine = engine
            app.state.knowledge = KnowledgeBase(engine, config)
            app.state.llm = llm
            app.state.chat = ChatService(app.state.knowledge, llm)
            yield
        finally:
            await run_in_threadpool(llm.close)
            engine.dispose()

    app = FastAPI(title="DocuMind AI", version="0.4.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Accept", "Content-Type"],
    )
    @app.middleware("http")
    async def restrict_browser_writes(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and origin is not None
            and origin != str(request.base_url).rstrip("/")
            and origin not in config.cors_origins
        ):
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "origin_forbidden", "message": "Use the local DocuMind frontend to modify the library."}},
            )
        return await call_next(request)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
    app.include_router(router)
    app.include_router(knowledge_router)
    app.include_router(chat_router)

    @app.exception_handler(KnowledgeError)
    async def knowledge_error(_request: Request, exc: KnowledgeError):
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("Database operation failed for %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "database_unavailable", "message": "The local database is unavailable."}},
        )

    return app


app = create_app()
