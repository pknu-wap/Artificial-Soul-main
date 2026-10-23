"""Explicit real E5 + Qdrant verification using only a test-owned collection."""

import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient

from app.core.config import BACKEND_DIR, Settings
from app.document.ingestion import prepare_txt_ingestion
from app.main import create_app
from app.rag.embedding import E5EmbeddingProvider
from app.rag.indexing import index_knowledge

pytestmark = [
    pytest.mark.integration,
    pytest.mark.rag_integration,
    pytest.mark.skipif(os.environ.get("RUN_RAG_INTEGRATION") != "1", reason="Set RUN_RAG_INTEGRATION=1 after preparing E5 and starting Qdrant"),
]


async def test_actual_embedding_index_reindex_search_and_http():
    name = f"test_rag_e5_{uuid4().hex}"
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://test:test@127.0.0.1:1/test",
        QDRANT_URL=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333"),
        QDRANT_COLLECTION_NAME=name, QDRANT_VECTOR_SIZE=384, QDRANT_DISTANCE="Cosine",
    )
    prepared = prepare_txt_ingestion(
        BACKEND_DIR / "examples" / "knowledge" / "university.txt",
        source="examples/university.txt", splitter=str.splitlines,
        category="sample", metadata={"sample": True},
    )
    provider = E5EmbeddingProvider(settings)
    client = AsyncQdrantClient(url=str(settings.qdrant_url), timeout=10, check_compatibility=False)
    owns_name = False
    try:
        assert not await client.collection_exists(name)
        owns_name = True
        vector = await provider.embed_query("장학금 신청 방법을 알려주세요")
        assert len(vector) == 384
        assert sum(value * value for value in vector) == pytest.approx(1.0, abs=1e-5)
        assert await index_knowledge(prepared, client, provider, settings) == 4
        assert (await client.count(name, exact=True)).count == 4
        assert await index_knowledge(prepared, client, provider, settings) == 4
        assert (await client.count(name, exact=True)).count == 4
        records, _ = await client.scroll(name, limit=10, with_payload=True, with_vectors=True)
        assert {str(record.id) for record in records} == {str(chunk.id) for chunk in prepared.chunks}
        for record in records:
            assert len(record.vector) == 384
            assert not record.payload["text"].startswith("passage: ")
            assert record.payload["source"] == "examples/university.txt"

        application = create_app(settings)
        async with application.router.lifespan_context(application):
            # The HTTP path uses its own lazy, cache-only provider and real Qdrant.
            async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as http:
                response = await http.post("/api/rag/retrieve", json={"question": "장학금 신청 방법을 알려주세요", "top_k": 3})
                assert response.status_code == 200, response.text
                hits = response.json()["results"]
                assert len(hits) == 3
                assert [hit["score"] for hit in hits] == sorted((hit["score"] for hit in hits), reverse=True)
                assert {hit["chunk_id"] for hit in hits} <= {str(chunk.id) for chunk in prepared.chunks}
                assert all(hit["source"] == "examples/university.txt" for hit in hits)
                assert all(hit["metadata"] == {"sample": True} for hit in hits)
                assert "answer" not in response.json()
                print("\nSample quality observation (not a quality benchmark):", [(hit["chunk_index"], round(hit["score"], 4)) for hit in hits])
                assert (await http.get("/health")).json() == {"status": "ok"}
    finally:
        try:
            if owns_name and await client.collection_exists(name):
                await client.delete_collection(name)
                assert not await client.collection_exists(name)
        finally:
            await provider.aclose()
            await client.close()
