"""Explicit test settings and async infrastructure doubles."""

from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app import main
from app.core.config import Settings
from qdrant_client import models
from app.rag.indexing import EMBEDDING_METADATA_KEY


@pytest.fixture
def settings() -> Settings:
    # Ignore .env entirely. Port 1 is intentionally unrelated to local infra.
    return Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://test:test@127.0.0.1:1/test",
        QDRANT_URL="http://127.0.0.1:1",
        HEALTH_CHECK_TIMEOUT_SECONDS=0.05,
        QDRANT_COLLECTION_NAME="test_knowledge",
        QDRANT_VECTOR_SIZE=None,
        QDRANT_DISTANCE="Cosine",
    )


@pytest_asyncio.fixture
async def infrastructure_client(monkeypatch, settings):
    engine = MagicMock(spec=AsyncEngine)
    engine.dispose = AsyncMock()
    connection = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = 1
    connection.execute.return_value = result
    engine.connect.return_value.__aenter__.return_value = connection

    qdrant = AsyncMock(spec=AsyncQdrantClient)
    monkeypatch.setattr(main, "create_engine", lambda config: engine)
    monkeypatch.setattr(main, "create_qdrant_client", lambda config: qdrant)
    application = main.create_app(settings)

    # HTTPX ASGITransport does not run lifespan automatically.
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            yield client, engine, connection, qdrant

    engine.dispose.assert_awaited_once()
    qdrant.close.assert_awaited_once()


@pytest.fixture
def rag_resources(settings):
    config = settings.model_copy(update={"qdrant_vector_size": 384})
    vector = [1.0] + [0.0] * 383
    provider = SimpleNamespace(
        dimension=384, identity="test-e5@fixed-revision",
        embed_query=AsyncMock(return_value=vector),
        embed_documents=AsyncMock(side_effect=lambda texts: [vector[:] for _ in texts]),
    )
    qdrant = AsyncMock(spec=AsyncQdrantClient)
    qdrant.collection_exists.return_value = True
    qdrant.create_collection.return_value = True
    qdrant.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(vectors=models.VectorParams(size=384, distance=models.Distance.COSINE), sparse_vectors=None),
            metadata={EMBEDDING_METADATA_KEY: provider.identity},
        ), points_count=0,
    )
    qdrant.query_points.return_value = SimpleNamespace(points=[])
    qdrant.upsert.return_value = models.UpdateResult(operation_id=1, status=models.UpdateStatus.COMPLETED)

    async def set_metadata(**kwargs):
        qdrant.get_collection.return_value.config.metadata = kwargs["metadata"]
        return True

    qdrant.update_collection.side_effect = set_metadata
    return config, qdrant, provider


@pytest_asyncio.fixture
async def retrieval_client(monkeypatch, rag_resources):
    from app.rag.service import RetrievalService

    config, qdrant, provider = rag_resources
    engine = MagicMock(spec=AsyncEngine)
    engine.dispose = AsyncMock()
    monkeypatch.setattr(main, "create_engine", lambda settings: engine)
    monkeypatch.setattr(main, "create_qdrant_client", lambda settings: qdrant)
    application = main.create_app(config)
    async with application.router.lifespan_context(application):
        application.state.retrieval_service = RetrievalService(config, qdrant, provider)
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
            yield client, qdrant, provider
    engine.dispose.assert_awaited_once()
    qdrant.close.assert_awaited_once()
