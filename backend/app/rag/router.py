"""Local-development retrieval API. No authentication or generated answer yet."""

import logging

from fastapi import APIRouter, Depends, Request

from app.rag.errors import RagError
from app.rag.schema import RetrievalRequest, RetrievalResponse
from app.rag.service import RetrievalService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["RAG retrieval (development)"])


def get_retrieval_service(request: Request) -> RetrievalService:
    return request.app.state.retrieval_service


@router.post(
    "/retrieve", response_model=RetrievalResponse,
    summary="Search knowledge chunks (local development only)",
    responses={422: {"description": "Invalid input"}, 503: {"description": "Retrieval not ready"},
               504: {"description": "Retrieval timed out"}, 500: {"description": "Invalid stored data or internal failure"}},
)
async def retrieve(
    body: RetrievalRequest, service: RetrievalService = Depends(get_retrieval_service),
) -> RetrievalResponse:
    try:
        return await service.retrieve(body)
    except RagError:
        raise
    except Exception as error:
        logger.error("Retrieval failed (%s)", type(error).__name__)
        raise RagError(500, "INTERNAL_ERROR", "검색 처리 중 오류가 발생했습니다.") from error
