"""Opt-in network verification; only a unique, test-owned collection is changed."""

import os
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from app.clients.qdrant import ensure_collection, upsert_chunks
from app.document.ingestion import prepare_txt_ingestion

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_QDRANT_INTEGRATION") != "1",
        reason="Set RUN_QDRANT_INTEGRATION=1 to use a running Qdrant server",
    ),
]


async def test_qdrant_ingestion_and_reingestion(tmp_path):
    path = tmp_path / "academic.txt"
    path.write_text("등록 일정\n장학 안내\n", encoding="utf-8")
    prepared = prepare_txt_ingestion(
        path, source="tests/academic.txt", splitter=str.splitlines,
        category="academic", metadata={"year": 2026},
    )
    # Synthetic 2D vectors are exclusively for this test, never production embeddings.
    vectors = [[1.0, 0.0], [0.0, 1.0]]
    collection_name = f"test_txt_ingestion_{uuid4().hex}"
    client = AsyncQdrantClient(
        url=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333"),
        timeout=10, check_compatibility=False,
    )
    owns_name = False
    try:
        assert not await client.collection_exists(collection_name)
        owns_name = True
        await ensure_collection(client, collection_name=collection_name, vector_size=2)
        # This second preparation must reuse the existing collection.
        await ensure_collection(client, collection_name=collection_name, vector_size=2)
        assert (await client.count(collection_name, exact=True)).count == 0
        assert await upsert_chunks(client, prepared.chunks, vectors, collection_name=collection_name, vector_size=2) == 2
        assert (await client.count(collection_name, exact=True)).count == 2

        changed = [prepared.chunks[0].model_copy(update={"text": "등록 일정 변경"}), prepared.chunks[1]]
        assert await upsert_chunks(client, changed, vectors, collection_name=collection_name, vector_size=2) == 2
        assert (await client.count(collection_name, exact=True)).count == 2
        records, next_page = await client.scroll(
            collection_name, limit=10, with_vectors=True, with_payload=True
        )
        assert next_page is None
        by_id = {str(record.id): record for record in records}
        assert set(by_id) == {str(chunk.id) for chunk in changed}
        for chunk, vector in zip(changed, vectors, strict=True):
            stored = by_id[str(chunk.id)]
            assert stored.payload == chunk.model_dump(mode="json", exclude={"id"})
            assert stored.vector == pytest.approx(vector)
    finally:
        try:
            if owns_name and await client.collection_exists(collection_name):
                await client.delete_collection(collection_name)
                assert not await client.collection_exists(collection_name)
        finally:
            await client.close()
