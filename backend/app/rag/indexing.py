"""Explicit knowledge indexing; never invoked by startup or a search request."""

from qdrant_client import AsyncQdrantClient, models

from app.clients.qdrant import ensure_collection, upsert_chunks, validate_collection_config
from app.core.config import Settings
from app.document.schema import IngestionResult
from app.rag.embedding import EmbeddingProvider, validate_embeddings
from app.rag.errors import RetrievalConfigurationError

EMBEDDING_METADATA_KEY = "artificial_soul_embedding"


def validate_index_settings(settings: Settings, provider: EmbeddingProvider) -> None:
    if (
        settings.qdrant_vector_size != provider.dimension
        or settings.qdrant_distance != models.Distance.COSINE
        or not settings.qdrant_collection_name.strip()
    ):
        raise RetrievalConfigurationError()


def validate_index_collection(collection, settings: Settings, provider: EmbeddingProvider) -> None:
    try:
        validate_collection_config(collection, provider.dimension, settings.qdrant_distance)
    except ValueError as error:
        raise RetrievalConfigurationError() from error
    if (collection.config.metadata or {}).get(EMBEDDING_METADATA_KEY) != provider.identity:
        raise RetrievalConfigurationError()


async def index_knowledge(
    prepared: IngestionResult,
    client: AsyncQdrantClient,
    provider: EmbeddingProvider,
    settings: Settings,
) -> int:
    validate_index_settings(settings, provider)
    vectors = validate_embeddings(
        await provider.embed_documents([chunk.text for chunk in prepared.chunks]),
        len(prepared.chunks), provider.dimension,
    )
    # Existing unmarked collections are deliberately not adopted, even when empty.
    # A model-specific collection must be created by this explicit indexing path.
    existed = await client.collection_exists(collection_name=settings.qdrant_collection_name)
    if existed:
        collection = await client.get_collection(collection_name=settings.qdrant_collection_name)
        validate_index_collection(collection, settings, provider)
    await ensure_collection(
        client, collection_name=settings.qdrant_collection_name,
        vector_size=provider.dimension, distance=settings.qdrant_distance,
    )
    if not existed:
        collection = await client.get_collection(collection_name=settings.qdrant_collection_name)
        metadata = collection.config.metadata or {}
        current = metadata.get(EMBEDDING_METADATA_KEY)
        if current is not None and current != provider.identity:
            raise RetrievalConfigurationError()
        if current is None:
            if collection.points_count != 0:
                raise RetrievalConfigurationError()
            updated = await client.update_collection(
                collection_name=settings.qdrant_collection_name,
                metadata={**metadata, EMBEDDING_METADATA_KEY: provider.identity},
            )
            if not updated:
                raise RetrievalConfigurationError()
        collection = await client.get_collection(collection_name=settings.qdrant_collection_name)
        validate_index_collection(collection, settings, provider)
    return await upsert_chunks(
        client, prepared.chunks, vectors,
        collection_name=settings.qdrant_collection_name, vector_size=provider.dimension,
    )
