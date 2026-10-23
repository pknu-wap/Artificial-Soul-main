import asyncio
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import torch

from app.rag.embedding import E5EmbeddingProvider, _snapshot_path, prepare_model, validate_embeddings
from app.rag.errors import EmbeddingInputError, EmbeddingUnavailable, RetrievalConfigurationError


class ToyTokenizer:
    def __init__(self, length=3):
        self.length = length
        self.inputs = []

    def __call__(self, texts, **options):
        self.inputs.append((texts, options))
        ids = torch.ones((len(texts), self.length), dtype=torch.long)
        mask = torch.zeros_like(ids)
        mask[:, :2] = 1
        return {"input_ids": ids, "attention_mask": mask}


class ToyModel:
    config = SimpleNamespace(hidden_size=384)

    def to(self, device):
        return self

    def eval(self):
        return self

    def __call__(self, input_ids, attention_mask):
        assert torch.is_inference_mode_enabled()
        batch, length = input_ids.shape
        hidden = torch.full((batch, length, 384), 999.0)
        hidden[:, 0] = 0
        hidden[:, 1] = 0
        hidden[:, 0, 0] = 1
        hidden[:, 1, 1] = 1
        return SimpleNamespace(last_hidden_state=hidden)


@pytest.fixture
def toy_provider(settings, monkeypatch):
    provider = E5EmbeddingProvider(settings.model_copy(update={"embedding_batch_size": 2}))
    tokenizer, model = ToyTokenizer(), ToyModel()

    def load():
        provider._tokenizer, provider._model = tokenizer, model

    monkeypatch.setattr(provider, "_load_sync", load)
    return provider, tokenizer


async def test_prefix_pooling_normalization_and_original_input(toy_provider):
    provider, tokenizer = toy_provider
    texts = ["  장학금 안내  ", "수강신청 안내", "도서관 안내"]
    vectors = await provider.embed_documents(texts)
    query = await provider.embed_query("장학금 신청")
    assert [batch for batch, _ in tokenizer.inputs] == [
        ["passage:   장학금 안내  ", "passage: 수강신청 안내"],
        ["passage: 도서관 안내"], ["query: 장학금 신청"],
    ]
    assert texts[0] == "  장학금 안내  "
    assert len(vectors) == 3
    for vector in [*vectors, query]:
        assert len(vector) == 384
        assert vector[:2] == pytest.approx([2 ** -0.5, 2 ** -0.5])
        assert vector[2:] == [0.0] * 382
        assert sum(value * value for value in vector) == pytest.approx(1.0)
    assert all(options["truncation"] is False for _, options in tokenizer.inputs)


@pytest.mark.parametrize("length,allowed", [(512, True), (513, False)])
async def test_exact_token_limit_including_prefix_and_special_tokens(toy_provider, length, allowed):
    provider, tokenizer = toy_provider
    tokenizer.length = length
    if allowed:
        assert len(await provider.embed_query("입력")) == 384
    else:
        with pytest.raises(EmbeddingInputError):
            await provider.embed_query("입력")


@pytest.mark.parametrize("bad", ["", " \n\t", None, 1])
async def test_invalid_text_is_rejected_before_loading(settings, monkeypatch, bad):
    provider = E5EmbeddingProvider(settings)
    load = Mock(side_effect=AssertionError("must not load"))
    monkeypatch.setattr(provider, "_load_sync", load)
    with pytest.raises(EmbeddingInputError):
        await provider.embed_query(bad)
    load.assert_not_called()


async def test_empty_documents_do_not_load_model(settings, monkeypatch):
    provider = E5EmbeddingProvider(settings)
    load = Mock()
    monkeypatch.setattr(provider, "_load_sync", load)
    assert await provider.embed_documents([]) == []
    load.assert_not_called()
    with pytest.raises(EmbeddingInputError):
        await provider.embed_documents("one string")


@pytest.mark.parametrize("vectors", [
    [], [[1]], [[1, 0], [0, 1]], [[0, 0]], [[True, 1]], [["1", 0]],
    [[float("nan"), 1]], [[float("inf"), 1]], [[10 ** 400, 1]], None, "bad",
])
def test_complete_embedding_output_validation(vectors):
    with pytest.raises(EmbeddingUnavailable):
        validate_embeddings(vectors, count=1, dimension=2)


async def test_missing_local_model_does_not_download(settings, tmp_path, monkeypatch):
    import huggingface_hub
    download = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(huggingface_hub, "snapshot_download", download)
    provider = E5EmbeddingProvider(settings.model_copy(update={"embedding_cache_dir": tmp_path}))
    with pytest.raises(EmbeddingUnavailable):
        await provider.embed_query("장학금")
    download.assert_not_called()


async def test_loader_reuses_local_revision_and_serializes_first_load(settings, tmp_path, monkeypatch):
    import transformers
    config = settings.model_copy(update={"embedding_cache_dir": tmp_path})
    path = _snapshot_path(config)
    path.mkdir(parents=True)
    for name in ("config.json", "tokenizer.json", "model.safetensors", "tokenizer_config.json"):
        (path / name).write_text("{}")
    tokenizer = ToyTokenizer()
    model = Mock(wraps=ToyModel())
    model.config.hidden_size = 384
    tokenizer_loader = Mock(return_value=tokenizer)
    model_loader = Mock(return_value=model)
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", tokenizer_loader)
    monkeypatch.setattr(transformers.AutoModel, "from_pretrained", model_loader)
    provider = E5EmbeddingProvider(config)
    # Run real tokenizer/pooling/inference orchestration; only weights are synthetic.
    await asyncio.gather(*(provider.embed_query("질문") for _ in range(4)))
    tokenizer_loader.assert_called_once_with(str(path), local_files_only=True, trust_remote_code=False)
    model_loader.assert_called_once_with(str(path), local_files_only=True, trust_remote_code=False, use_safetensors=True)
    model.eval.assert_called_once()
    model.to.assert_called_once_with("cpu")
    await provider.aclose()
    assert provider._model is None and provider._tokenizer is None


def test_prepare_model_is_explicit_pinned_and_filters_files(settings, tmp_path, monkeypatch):
    import huggingface_hub
    download = Mock(return_value=str(tmp_path))
    monkeypatch.setattr(huggingface_hub, "snapshot_download", download)
    assert prepare_model(settings) == tmp_path
    arguments = download.call_args.kwargs
    assert arguments["revision"] == settings.embedding_model_revision
    assert arguments["repo_id"] == "intfloat/multilingual-e5-small"
    assert "model.safetensors" in arguments["allow_patterns"]
    assert "pytorch_model.bin" not in arguments["allow_patterns"]


async def test_non_e5_model_requires_a_different_provider(settings):
    provider = E5EmbeddingProvider(settings.model_copy(update={"embedding_model_id": "another/model"}))
    with pytest.raises(RetrievalConfigurationError):
        await provider.embed_query("질문")


def test_identity_changes_when_revision_changes(settings):
    first = E5EmbeddingProvider(settings)
    second = E5EmbeddingProvider(settings.model_copy(update={"embedding_model_revision": "0" * 40}))
    assert first.identity != second.identity


async def test_cancelled_cpu_call_keeps_lock_and_event_loop_responsive(toy_provider):
    provider, _ = toy_provider
    started, release = Event(), Event()
    calls = []
    original_load = provider._load_sync

    class BlockingModel(ToyModel):
        def __call__(self, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                started.set()
                assert release.wait(timeout=3)
            return super().__call__(**kwargs)

    def load():
        original_load()
        provider._model = BlockingModel()

    provider._load_sync = load
    first = asyncio.create_task(provider.embed_query("첫 질문"))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(provider.embed_query("둘째 질문"))
        await asyncio.sleep(0.03)
        assert calls == [1]  # CPU task still owns the lock after HTTP cancellation.
        release.set()
        assert len(await asyncio.wait_for(second, 2)) == 384
    finally:
        release.set()
        await provider.aclose()
    with pytest.raises(EmbeddingUnavailable):
        await provider.embed_query("종료 후 질문")
