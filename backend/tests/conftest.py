"""Explicit test settings and async infrastructure doubles."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app import main
from app.core.config import Settings


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
