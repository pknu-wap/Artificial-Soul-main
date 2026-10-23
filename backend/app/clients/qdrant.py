"""Qdrant lifecycle, explicit collection preparation, and Chunk storage."""

from collections.abc import Sequence
from math import ceil, isfinite
from numbers import Real

from qdrant_client import AsyncQdrantClient, models

from app.core.config import Settings
from app.document.schema import Chunk


def create_qdrant_client(settings: Settings) -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=str(settings.qdrant_url),
        timeout=ceil(settings.qdrant_request_timeout_seconds),
        # Avoid the constructor's network version check. Versions are pinned,
        # and readiness checks connectivity explicitly when requested.
        check_compatibility=False,
    )


async def check_qdrant(client: AsyncQdrantClient) -> None:
    # An empty collection list is healthy. Do not create a collection here.
    await client.get_collections()


def _validate_collection_parameters(
    collection_name: str, vector_size: int | None
) -> int:
    if not isinstance(collection_name, str) or not collection_name.strip():
        raise ValueError("collection_name must contain non-whitespace text")
    if type(vector_size) is not int or vector_size <= 0:
        raise ValueError("vector_size must be set to a positive integer")
    return vector_size


async def ensure_collection(
    client: AsyncQdrantClient,
    *,
    collection_name: str,
    vector_size: int | None,
    distance: models.Distance = models.Distance.COSINE,
) -> None:
    """Create a missing collection or validate an existing unnamed dense vector."""
    size = _validate_collection_parameters(collection_name, vector_size)
    distance = models.Distance(distance)
    if not await client.collection_exists(collection_name=collection_name):
        created = await client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=size, distance=distance),
        )
        if not created:
            raise RuntimeError("Qdrant collection creation did not complete")

    # Inspect both new and existing collections without deleting any data.
    collection = await client.get_collection(collection_name=collection_name)
    validate_collection_config(collection, size, distance)


def validate_collection_config(
    collection: models.CollectionInfo, size: int, distance: models.Distance
) -> None:
    """Shared read-only validation for indexing and retrieval."""
    params = collection.config.params
    vectors = params.vectors
    if (
        not isinstance(vectors, models.VectorParams)
        or vectors.multivector_config is not None
        or params.sparse_vectors
    ):
        raise ValueError("Collection must use one unnamed dense vector only")
    if vectors.size != size or vectors.distance != distance:
        raise ValueError("Collection vector size or distance does not match")


async def upsert_chunks(
    client: AsyncQdrantClient,
    chunks: Sequence[Chunk],
    vectors: Sequence[Sequence[float]],
    *,
    collection_name: str,
    vector_size: int | None,
) -> int:
    """Store caller-supplied embeddings; return processed Chunk count, not new IDs."""
    if len(chunks) != len(vectors):
        raise ValueError("Chunk and Vector counts must match")
    if not chunks:
        return 0
    size = _validate_collection_parameters(collection_name, vector_size)

    points: list[models.PointStruct] = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        if len(vector) != size:
            raise ValueError("Each Vector must match vector_size")
        values: list[float] = []
        for component in vector:
            if isinstance(component, bool) or not isinstance(component, Real):
                raise ValueError("Vector components must be finite real numbers")
            try:
                value = float(component)
            except (ValueError, OverflowError) as error:
                raise ValueError(
                    "Vector components must be finite real numbers"
                ) from error
            if not isfinite(value):
                raise ValueError("Vector components must be finite real numbers")
            values.append(value)
        points.append(
            models.PointStruct(
                id=str(chunk.id),
                vector=values,
                payload=chunk.model_dump(mode="json", exclude={"id"}),
            )
        )

    # Validate the whole input before writing and wait for application, not just ACK.
    result = await client.upsert(
        collection_name=collection_name, points=points, wait=True
    )
    if result.status != models.UpdateStatus.COMPLETED:
        raise RuntimeError("Qdrant upsert did not complete")
    return len(points)
