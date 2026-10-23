"""Adapt an NLP-owned splitter to the application's Chunk structure."""

from collections.abc import Callable, Sequence
from uuid import uuid5

from app.document.schema import Chunk, Document

TextSplitter = Callable[[str], Sequence[str]]


def chunk_document(document: Document, splitter: TextSplitter) -> list[Chunk]:
    texts = splitter(document.text)
    if isinstance(texts, (str, bytes)) or not isinstance(texts, Sequence):
        raise TypeError("splitter must return a sequence of strings")

    chunks: list[Chunk] = []
    for text in texts:
        if not isinstance(text, str):
            raise TypeError("each splitter result must be a string")
        if not text.strip():
            continue
        index = len(chunks)
        chunks.append(
            Chunk(
                id=uuid5(document.id, str(index)),
                document_id=document.id,
                text=text,
                chunk_index=index,
                source=document.source,
                category=document.category,
                metadata=document.metadata,
            )
        )
    if not chunks:
        raise ValueError("splitter must produce at least one non-blank chunk")
    return chunks
