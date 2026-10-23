"""Prepare TXT knowledge for a later embedding and indexing step."""

from pathlib import Path

from app.document.chunker import TextSplitter, chunk_document
from app.document.loader import load_txt
from app.document.schema import IngestionResult, Metadata


def prepare_txt_ingestion(
    path: str | Path,
    *,
    source: str,
    splitter: TextSplitter,
    category: str | None = None,
    metadata: Metadata | None = None,
) -> IngestionResult:
    document = load_txt(path, source=source, category=category, metadata=metadata)
    return IngestionResult(document=document, chunks=chunk_document(document, splitter))
