"""Application assembly and lifecycle management."""

from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.clients.qdrant import create_qdrant_client
from app.core.config import Settings
from app.core.database import create_engine, create_session_factory
from app.health.router import router as health_router
from app.rag.embedding import E5EmbeddingProvider
from app.rag.errors import RagError
from app.rag.router import router as rag_router
from app.rag.service import RetrievalService


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config = settings if settings is not None else Settings()
        # ExitStack releases both resources, including on partial startup failure.
        async with AsyncExitStack() as resources:
            engine = create_engine(config)
            resources.push_async_callback(engine.dispose)
            qdrant_client = create_qdrant_client(config)
            resources.push_async_callback(qdrant_client.close)
            embedding_provider = E5EmbeddingProvider(config)
            resources.push_async_callback(embedding_provider.aclose)

            application.state.settings = config
            application.state.engine = engine
            application.state.session_factory = create_session_factory(engine)
            application.state.qdrant_client = qdrant_client
            application.state.retrieval_service = RetrievalService(config, qdrant_client, embedding_provider)
            yield

    application = FastAPI(
        title="Artificial Soul API", version="0.1.0", lifespan=lifespan
    )
    application.include_router(health_router)
    application.include_router(rag_router)

    @application.exception_handler(RagError)
    async def handle_rag_error(request: Request, error: RagError):
        return JSONResponse(status_code=error.status_code, content={"detail": {"code": error.code, "message": error.message}})

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, error: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": {"code": "VALIDATION_ERROR", "message": "요청 입력 형식을 확인해 주세요."}})

    return application


# Importing the app does not load .env or contact external infrastructure.
app = create_app()
