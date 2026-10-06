from datetime import datetime
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.document.chunker import chunk_document
from app.document.ingestion import prepare_txt_ingestion
from app.document.loader import load_txt
from app.document.schema import Chunk, Document, IngestionResult


@pytest.fixture
def document():
    return Document(
        id=uuid4(), text="등록 일정\n장학 안내\n", source="academic/calendar.txt",
        category="academic", metadata={"year": 2026, "tags": ["학사"]},
    )


@pytest.mark.parametrize("record_type", [Document, Chunk])
@pytest.mark.parametrize("field", ["text", "source"])
@pytest.mark.parametrize("blank", ["", " \n\t"])
def test_records_reject_blank_text_and_source(record_type, field, blank):
    values = {"id": uuid4(), "text": "학사 안내", "source": "academic.txt"}
    if record_type is Chunk:
        values.update(document_id=uuid4(), chunk_index=0)
    values[field] = blank
    with pytest.raises(ValidationError):
        record_type(**values)


@pytest.mark.parametrize("bad_index", [-1, True, 0.5, "0"])
def test_chunk_index_is_a_non_negative_integer(document, bad_index):
    with pytest.raises(ValidationError):
        Chunk(
            id=uuid4(), document_id=document.id, text="학사 안내",
            source=document.source, chunk_index=bad_index,
        )


@pytest.mark.parametrize(
    "bad_value",
    [{"set"}, b"bytes", datetime(2026, 1, 1), float("nan"), float("inf")],
    ids=["set", "bytes", "datetime", "nan", "infinity"],
)
def test_metadata_must_be_json_compatible_and_finite(bad_value):
    with pytest.raises(ValidationError):
        Document(id=uuid4(), text="학사 안내", source="academic.txt", metadata={"bad": bad_value})


def test_metadata_defaults_and_nested_values_are_not_shared(document):
    first = Document(id=uuid4(), text="첫 문서", source="first.txt")
    second = Document(id=uuid4(), text="둘째 문서", source="second.txt")
    first.metadata["new"] = True
    assert second.metadata == {}

    chunks = chunk_document(document, str.splitlines)
    chunks[0].metadata["tags"].append("변경")
    assert document.metadata["tags"] == ["학사"]
    assert chunks[1].metadata["tags"] == ["학사"]
    assert isinstance(chunks[0].id, UUID)
    assert isinstance(chunks[0].model_dump(mode="json")["id"], str)


@pytest.mark.parametrize("name, bom", [("academic.txt", False), ("academic.TXT", True)])
def test_loader_reads_utf8_and_preserves_korean_whitespace_and_newlines(tmp_path, name, bom):
    path = tmp_path / name
    text = "  등록 일정\r\n장학 안내\n"
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    result = load_txt(path, source="academic/calendar.txt", category="academic", metadata={"year": 2026})
    assert result.text == text
    assert result.source == "academic/calendar.txt"
    assert str(tmp_path) not in result.source
    assert result.category == "academic"
    assert result.metadata == {"year": 2026}


def test_document_id_uses_source_rather_than_local_path_or_contents(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("원문", encoding="utf-8")
    second.write_text("변경된 원문", encoding="utf-8")
    original = load_txt(first, source="stable/source.txt")
    changed = load_txt(second, source="stable/source.txt")
    different_source = load_txt(first, source="another/source.txt")
    assert original.id == changed.id
    assert original.id != different_source.id


def test_loader_reports_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_txt(tmp_path / "missing.txt", source="missing.txt")


def test_loader_reports_directory(tmp_path):
    with pytest.raises(IsADirectoryError):
        load_txt(tmp_path, source="directory.txt")


def test_loader_rejects_unsupported_extension(tmp_path):
    path = tmp_path / "academic.md"
    path.write_text("학사 안내", encoding="utf-8")
    with pytest.raises(ValueError, match="Only .txt"):
        load_txt(path, source="academic.md")


def test_loader_does_not_ignore_decoding_errors(tmp_path):
    path = tmp_path / "academic.txt"
    path.write_bytes(b"\xff\xfeinvalid")
    with pytest.raises(UnicodeDecodeError):
        load_txt(path, source="academic.txt")


@pytest.mark.parametrize("contents", [b"", b" \r\n\t", b"\xef\xbb\xbf"])
def test_loader_rejects_empty_content(tmp_path, contents):
    path = tmp_path / "academic.txt"
    path.write_bytes(contents)
    with pytest.raises(ValueError, match="TXT file must contain"):
        load_txt(path, source="academic.txt")


def test_chunker_passes_original_text_and_preserves_order_and_metadata(document):
    splitter = Mock(return_value=["", " 첫 Chunk ", "\t", "둘째 Chunk"])
    chunks = chunk_document(document, splitter)
    splitter.assert_called_once_with(document.text)
    assert [chunk.text for chunk in chunks] == [" 첫 Chunk ", "둘째 Chunk"]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert len({chunk.id for chunk in chunks}) == 2
    for chunk in chunks:
        assert chunk.document_id == document.id
        assert chunk.source == document.source
        assert chunk.category == document.category
        assert chunk.metadata == document.metadata
    assert [chunk.id for chunk in chunk_document(document, splitter)] == [chunk.id for chunk in chunks]


@pytest.mark.parametrize("parts", [[], ["", " \n"]])
def test_chunker_rejects_an_empty_result(document, parts):
    with pytest.raises(ValueError, match="at least one"):
        chunk_document(document, lambda text: parts)


@pytest.mark.parametrize("parts", ["one string", b"bytes", ["valid", None], iter(["generator"])])
def test_chunker_rejects_an_invalid_splitter_contract(document, parts):
    with pytest.raises(TypeError):
        chunk_document(document, lambda text: parts)


def test_ingestion_prepares_records_without_settings_or_qdrant(tmp_path, monkeypatch):
    from app.clients import qdrant
    from app.core.config import Settings

    def fail_if_called(*args, **kwargs):
        pytest.fail("TXT preparation must not access settings or Qdrant")

    monkeypatch.setattr(Settings, "__init__", fail_if_called)
    monkeypatch.setattr(qdrant, "AsyncQdrantClient", fail_if_called)
    monkeypatch.setattr(qdrant, "ensure_collection", fail_if_called)
    monkeypatch.setattr(qdrant, "upsert_chunks", fail_if_called)
    path = tmp_path / "academic.txt"
    path.write_text("등록 일정\n장학 안내\n", encoding="utf-8")
    result = prepare_txt_ingestion(
        path, source="academic.txt", splitter=str.splitlines,
        category="academic", metadata={"year": 2026},
    )
    repeated = prepare_txt_ingestion(
        path, source="academic.txt", splitter=str.splitlines,
        category="academic", metadata={"year": 2026},
    )
    assert isinstance(result, IngestionResult)
    assert result == repeated
    assert [chunk.text for chunk in result.chunks] == ["등록 일정", "장학 안내"]


def test_ingestion_result_requires_chunks(document):
    with pytest.raises(ValidationError):
        IngestionResult(document=document, chunks=[])
