"""Search-only HTTP DTOs. No generated answer or raw embedding is returned."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.document.schema import Metadata


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(
        min_length=1, max_length=10000, strict=True,
        examples=["장학금 신청 방법을 알려주세요"],
    )
    top_k: int = Field(default=5, ge=1, le=20, strict=True)

    @field_validator("question")
    @classmethod
    def require_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    chunk_id: UUID
    document_id: UUID
    chunk_index: int = Field(ge=0, strict=True)
    text: str
    source: str
    category: str | None
    metadata: Metadata
    score: float


class RetrievalResponse(BaseModel):
    question: str
    top_k: int
    results: list[RetrievedChunk]
