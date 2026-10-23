"""Lazy CPU E5 inference from an explicitly prepared, revision-pinned local cache."""

import asyncio
from collections.abc import Sequence
from math import isfinite
from numbers import Real
from pathlib import Path
from threading import Lock
from typing import Protocol

from app.core.config import E5_MODEL_ID, Settings
from app.rag.errors import EmbeddingInputError, EmbeddingUnavailable, RetrievalConfigurationError


class EmbeddingProvider(Protocol):
    dimension: int

    @property
    def identity(self) -> str: ...

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


def validate_embeddings(vectors: object, count: int, dimension: int) -> list[list[float]]:
    """Validate the complete result before any Qdrant write, including zero vectors."""
    if not isinstance(vectors, Sequence) or isinstance(vectors, (str, bytes)) or len(vectors) != count:
        raise EmbeddingUnavailable()
    checked: list[list[float]] = []
    for vector in vectors:
        if not isinstance(vector, Sequence) or isinstance(vector, (str, bytes)) or len(vector) != dimension:
            raise EmbeddingUnavailable()
        values: list[float] = []
        for component in vector:
            if isinstance(component, bool) or not isinstance(component, Real):
                raise EmbeddingUnavailable()
            try:
                number = float(component)
            except (ValueError, OverflowError) as error:
                raise EmbeddingUnavailable() from error
            if not isfinite(number):
                raise EmbeddingUnavailable()
            values.append(number)
        if not any(value != 0 for value in values):
            raise EmbeddingUnavailable()
        checked.append(values)
    return checked


def _snapshot_path(settings: Settings) -> Path:
    return settings.embedding_cache_dir / ("models--" + settings.embedding_model_id.replace("/", "--")) / "snapshots" / settings.embedding_model_revision


def prepare_model(settings: Settings) -> Path:
    """The only model-download entry point. Never called by import/startup/HTTP."""
    if settings.embedding_model_id != E5_MODEL_ID:
        raise RetrievalConfigurationError()
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(
        repo_id=settings.embedding_model_id,
        revision=settings.embedding_model_revision,
        cache_dir=str(settings.embedding_cache_dir),
        allow_patterns=[
            "config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
            "special_tokens_map.json", "sentencepiece.bpe.model",
        ],
    ))


class E5EmbeddingProvider:
    dimension = 384
    max_tokens = 512

    def __init__(self, settings: Settings):
        # No filesystem checks, torch import, tokenizer creation, or download here.
        self.settings = settings
        self._lock = Lock()
        self._tokenizer = None
        self._model = None
        self._closed = False

    @property
    def identity(self) -> str:
        return f"{self.settings.embedding_model_id}@{self.settings.embedding_model_revision}:e5-mean-mask-l2-v1"

    def _load_sync(self) -> None:
        if self._model is not None:
            return
        if self.settings.embedding_model_id != E5_MODEL_ID:
            raise RetrievalConfigurationError()
        snapshot = _snapshot_path(self.settings)
        if not all((snapshot / name).is_file() for name in ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json")):
            raise EmbeddingUnavailable()
        try:
            from transformers import AutoModel, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False)
            model = AutoModel.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False, use_safetensors=True)
            model.to("cpu")
            model.eval()
            if model.config.hidden_size != self.dimension:
                raise RetrievalConfigurationError()
        except RetrievalConfigurationError:
            raise
        except Exception as error:
            raise EmbeddingUnavailable() from error
        self._tokenizer, self._model = tokenizer, model

    def _embed_sync(self, texts: list[str], prefix: str) -> list[list[float]]:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingInputError()
        if not texts:
            return []
        # The lock stays inside the worker: cancelling HTTP does not release it
        # while CPU inference is still running in the background thread.
        with self._lock:
            if self._closed:
                raise EmbeddingUnavailable()
            self._load_sync()
            try:
                import torch
                import torch.nn.functional as functional

                vectors: list[list[float]] = []
                for start in range(0, len(texts), self.settings.embedding_batch_size):
                    batch = self._tokenizer(
                        [prefix + text for text in texts[start:start + self.settings.embedding_batch_size]],
                        padding=True, truncation=False, return_tensors="pt", return_attention_mask=True,
                    )
                    if batch["input_ids"].shape[1] > self.max_tokens:
                        raise EmbeddingInputError("접두사·특수 토큰을 포함해 최대 512토큰까지 입력할 수 있습니다.")
                    with torch.inference_mode():
                        hidden = self._model(**batch).last_hidden_state
                        mask = batch["attention_mask"]
                        hidden = hidden.masked_fill(~mask[..., None].bool(), 0.0)
                        pooled = hidden.sum(dim=1) / mask.sum(dim=1)[..., None]
                        normalized = functional.normalize(pooled, p=2, dim=1)
                        vectors.extend(normalized.float().cpu().tolist())
                return validate_embeddings(vectors, len(texts), self.dimension)
            except EmbeddingInputError:
                raise
            except Exception as error:
                raise EmbeddingUnavailable() from error

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if isinstance(texts, (str, bytes)):
            raise EmbeddingInputError()
        return await asyncio.to_thread(self._embed_sync, list(texts), "passage: ")

    async def embed_query(self, text: str) -> list[float]:
        return (await asyncio.to_thread(self._embed_sync, [text], "query: "))[0]

    def _close_sync(self) -> None:
        with self._lock:
            self._closed = True
            self._tokenizer = None
            self._model = None

    async def aclose(self) -> None:
        await asyncio.to_thread(self._close_sync)
