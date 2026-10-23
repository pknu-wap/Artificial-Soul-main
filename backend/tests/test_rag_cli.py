from unittest.mock import AsyncMock, Mock

import pytest

from app.rag import cli


def test_prepare_command_downloads_only_when_requested(monkeypatch, settings, tmp_path, capsys):
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    download = Mock(return_value=tmp_path)
    monkeypatch.setattr(cli, "prepare_model", download)
    assert cli.main(["prepare-model"]) == 0
    download.assert_called_once_with(settings)
    assert settings.embedding_model_revision in capsys.readouterr().out


def test_sample_splitter_and_injected_nlp_function():
    assert cli.resolve_splitter("lines")("a\nb") == ["a", "b"]
    assert cli.resolve_splitter("builtins:sorted")("ba") == ["a", "b"]
    with pytest.raises(ValueError):
        cli.resolve_splitter("bad-format")


async def test_index_cli_closes_provider_and_client_on_failure(monkeypatch, settings, tmp_path):
    from types import SimpleNamespace
    path = tmp_path / "sample.txt"
    path.write_text("자료", encoding="utf-8")
    client = SimpleNamespace(close=AsyncMock())
    provider = SimpleNamespace(aclose=AsyncMock())
    monkeypatch.setattr(cli, "E5EmbeddingProvider", lambda config: provider)
    monkeypatch.setattr(cli, "create_qdrant_client", lambda config: client)
    monkeypatch.setattr(cli, "index_knowledge", AsyncMock(side_effect=RuntimeError("failure")))
    args = SimpleNamespace(path=str(path), source="sample.txt", category=None, metadata="{}", splitter="lines")
    with pytest.raises(RuntimeError):
        await cli._index(args, settings)
    provider.aclose.assert_awaited_once()
    client.close.assert_awaited_once()


def test_cli_errors_do_not_expose_internal_exception(monkeypatch, settings, capsys):
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(cli, "prepare_model", Mock(side_effect=RuntimeError("private-password@internal-host")))
    assert cli.main(["prepare-model"]) == 1
    assert "private-password" not in capsys.readouterr().err
