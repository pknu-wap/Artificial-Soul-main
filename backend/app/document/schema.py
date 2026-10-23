"""Validated TXT knowledge records shared with the NLP pipeline."""

import json
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

Metadata = dict[str, JsonValue]
DOCUMENT_NAMESPACE = uuid5(NAMESPACE_URL, "artificial-soul:document")


class _KnowledgeText(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    text: str
    source: str
    category: str | None = None
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("text", "source")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must contain non-whitespace text")
        # Keep the original content and source identifier unchanged.
        return value

    @field_validator("metadata", mode="before")
    @classmethod
    def require_json_metadata(cls, value: object) -> object:
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(
                "metadata must contain JSON-compatible finite values"
            ) from error
        return value


class Document(_KnowledgeText):
    id: UUID


class Chunk(_KnowledgeText):
    id: UUID
    document_id: UUID
    chunk_index: int = Field(ge=0, strict=True)


class IngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: Document
    chunks: list[Chunk] = Field(min_length=1)
