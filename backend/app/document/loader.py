"""Read team-prepared UTF-8 TXT files without contacting infrastructure."""

from pathlib import Path
from stat import S_ISREG
from uuid import uuid5

from app.document.schema import DOCUMENT_NAMESPACE, Document, Metadata


def load_txt(
    path: str | Path,
    *,
    source: str,
    category: str | None = None,
    metadata: Metadata | None = None,
) -> Document:
    file_path = Path(path)
    # stat raises FileNotFoundError or PermissionError without masking the cause.
    file_stat = file_path.stat()
    if file_path.is_dir():
        raise IsADirectoryError("TXT input must be a file")
    if not S_ISREG(file_stat.st_mode):
        raise ValueError("TXT input must be a regular file")
    if file_path.suffix.lower() != ".txt":
        raise ValueError("Only .txt files are supported")

    # utf-8-sig removes a UTF-8 BOM; newline="" preserves CRLF and LF as written.
    with file_path.open(encoding="utf-8-sig", newline="") as file:
        text = file.read()
    if not text.strip():
        raise ValueError("TXT file must contain non-whitespace text")

    return Document(
        id=uuid5(DOCUMENT_NAMESPACE, source),
        text=text,
        source=source,
        category=category,
        metadata={} if metadata is None else metadata,
    )
