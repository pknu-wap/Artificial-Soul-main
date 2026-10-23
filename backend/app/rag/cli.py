"""Manual model preparation and TXT indexing. No HTTP ingestion endpoint."""

import argparse
import asyncio
import importlib
import json
import sys

from pydantic import ValidationError

from app.clients.qdrant import create_qdrant_client
from app.core.config import Settings
from app.document.ingestion import prepare_txt_ingestion
from app.rag.embedding import E5EmbeddingProvider, prepare_model
from app.rag.errors import RagError
from app.rag.indexing import index_knowledge


def resolve_splitter(spec: str):
    if spec == "lines":
        # Demonstration strategy only; an NLP splitter is injectable below.
        return str.splitlines
    module, separator, name = spec.partition(":")
    if not separator or not module or not name:
        raise ValueError("Use --splitter lines or package.module:function")
    splitter = getattr(importlib.import_module(module), name)
    if not callable(splitter):
        raise ValueError("splitter must be callable")
    return splitter


async def _index(args, settings: Settings) -> int:
    metadata = json.loads(args.metadata)
    prepared = prepare_txt_ingestion(
        args.path, source=args.source, category=args.category, metadata=metadata,
        splitter=resolve_splitter(args.splitter),
    )
    provider = E5EmbeddingProvider(settings)
    client = create_qdrant_client(settings)
    try:
        count = await index_knowledge(prepared, client, provider, settings)
        print(json.dumps({"processed_chunks": count, "document_id": str(prepared.document.id),
                          "collection": settings.qdrant_collection_name,
                          "embedding_identity": provider.identity}, ensure_ascii=False))
        return 0
    finally:
        try:
            await provider.aclose()
        finally:
            await client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare-model", help="Download the pinned E5 snapshot explicitly")
    index = commands.add_parser("index-txt", help="Prepare and index one TXT file")
    index.add_argument("path")
    index.add_argument("--source", required=True)
    index.add_argument("--category")
    index.add_argument("--metadata", default="{}", help="JSON object")
    index.add_argument("--splitter", required=True, help="lines (sample only) or package.module:function")
    args = parser.parse_args(argv)
    try:
        settings = Settings()
        if args.command == "prepare-model":
            path = prepare_model(settings)
            print(json.dumps({"model_id": settings.embedding_model_id,
                              "revision": settings.embedding_model_revision,
                              "snapshot": str(path)}, ensure_ascii=False))
            return 0
        return asyncio.run(_index(args, settings))
    except RagError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
    except ValidationError:
        print("입력 또는 환경설정 형식을 확인해 주세요.", file=sys.stderr)
    except Exception as error:
        # Avoid echoing raw file contents, connection URLs, or credential-bearing errors.
        print(f"작업에 실패했습니다 ({type(error).__name__}). 파일·설정·서비스 상태를 확인해 주세요.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
