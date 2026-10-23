"""Question embedding and retrieval orchestration. LLM answers are week four."""

import asyncio

from qdrant_client import AsyncQdrantClient

from app.core.config import Settings
from app.rag.embedding import EmbeddingProvider, validate_embeddings
from app.rag.errors import EmbeddingUnavailable, RagError, RetrievalTimeout
from app.rag.indexing import validate_index_settings
from app.rag.retrieval import retrieve_chunks
from app.rag.schema import RetrievalRequest, RetrievalResponse


class RetrievalService:
    def __init__(self, settings: Settings, client: AsyncQdrantClient, provider: EmbeddingProvider):
        self.settings = settings
        self.client = client
        self.provider = provider

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        validate_index_settings(self.settings, self.provider)
        try:
            async with asyncio.timeout(self.settings.retrieval_timeout_seconds):
                try:
                    output = await self.provider.embed_query(request.question)
                    vector = validate_embeddings([output], 1, self.provider.dimension)[0]
                except RagError:
                    raise
                except Exception as error:
                    raise EmbeddingUnavailable() from error
                hits = await retrieve_chunks(
                    self.client, vector, request.top_k, self.settings, self.provider,
                )
                return RetrievalResponse(question=request.question, top_k=request.top_k, results=hits)
        except TimeoutError as error:
            raise RetrievalTimeout() from error
