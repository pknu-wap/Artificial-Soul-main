"""Read-only dense retrieval and validation of stored Chunk payloads."""

import httpx
from pydantic import ValidationError
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.core.config import Settings
from app.document.schema import Chunk
from app.rag.embedding import EmbeddingProvider
from app.rag.errors import (
    CollectionNotReady, RagError, RetrievalDataError, RetrievalTimeout, SearchUnavailable,
)
from app.rag.indexing import validate_index_collection
from app.rag.schema import RetrievedChunk


async def retrieve_chunks(
    client: AsyncQdrantClient, vector: list[float], top_k: int,
    settings: Settings, provider: EmbeddingProvider,
) -> list[RetrievedChunk]:
    try:
        if not await client.collection_exists(collection_name=settings.qdrant_collection_name):
            raise CollectionNotReady()
        collection = await client.get_collection(collection_name=settings.qdrant_collection_name)
        validate_index_collection(collection, settings, provider)
        result = await client.query_points(
            collection_name=settings.qdrant_collection_name, query=vector,
            limit=top_k, with_payload=True, with_vectors=False,
        )
    except RagError:
        raise
    except (TimeoutError, httpx.TimeoutException) as error:
        raise RetrievalTimeout() from error
    except ResponseHandlingException as error:
        if isinstance(error.source, (TimeoutError, httpx.TimeoutException)):
            raise RetrievalTimeout() from error
        raise SearchUnavailable() from error
    except UnexpectedResponse as error:
        if error.status_code == 404:
            raise CollectionNotReady() from error
        raise SearchUnavailable() from error
    except Exception as error:
        raise SearchUnavailable() from error

    try:
        hits = []
        for point in result.points:
            if not isinstance(point.payload, dict) or "id" in point.payload:
                raise RetrievalDataError()
            chunk = Chunk.model_validate({"id": point.id, **point.payload})
            hits.append(RetrievedChunk(
                chunk_id=chunk.id, score=point.score,
                **chunk.model_dump(exclude={"id"}),
            ))
        return hits
    except (ValidationError, TypeError, ValueError, AttributeError) as error:
        raise RetrievalDataError() from error
