"""Read the four supported document formats into simple text records."""

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import hashlib
import re

import pandas as pd

from .config import MAX_FILE_MB, SUPPORTED_EXTENSIONS
from .errors import InvalidFileError, UnsupportedFileError


# This record gives every file one consistent shape after reading.
@dataclass
class DocumentRecord:
    """Normalized representation of one accepted upload."""

    name: str
    extension: str
    text: str
    source: str
    tables: list[pd.DataFrame] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def document_id(self) -> str:
        """Return a short stable ID based on the file name and extracted text."""
        return hashlib.sha256(f"{self.name}:{self.text}".encode("utf-8")).hexdigest()[
            :16
        ]


# Validate before parsing so unsupported or unsafe input fails with a friendly message.
def _safe_name(name: str) -> str:
    """Keep only the uploaded file name, never a user-provided path."""
    return Path(name).name or "uploaded_file"


def validate_upload(name: str, data: bytes) -> str:
    """Validate extension, size, content, and the basic PDF signature."""
    safe_name = _safe_name(name)
    extension = Path(safe_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedFileError(f"'{safe_name}' is not supported. Use: {allowed}.")
    if not data:
        raise InvalidFileError(f"'{safe_name}' is empty.")
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise InvalidFileError(
            f"'{safe_name}' is larger than the {MAX_FILE_MB:g} MB limit."
        )
    if extension == ".pdf" and not data.lstrip().startswith(b"%PDF"):
        raise InvalidFileError(f"'{safe_name}' does not look like a valid PDF.")
    return extension


# Convert tables to text because the RAG index searches text chunks.
def _clean_text(value: object) -> str:
    """Convert a table cell to compact, searchable text."""
    value = "" if value is None else str(value)
    return re.sub(r"\s+", " ", value).strip()


def _table_to_text(frame: pd.DataFrame, sheet_name: str = "") -> str:
    """Turn a DataFrame into text while retaining headers and row order."""
    if frame.empty:
        return ""
    frame = frame.fillna("")
    lines = []
    header = " | ".join(_clean_text(c) for c in frame.columns)
    if header.strip(" |"):
        lines.append(f"Sheet: {sheet_name}\nColumns: {header}")
    for _, row in frame.iterrows():
        values = [_clean_text(v) for v in row.tolist()]
        if any(values):
            lines.append(" | ".join(values))
    return "\n".join(lines)


# Read each supported extension and keep tables for the analysis panel.
def read_document(name: str, data: bytes) -> DocumentRecord:
    """Read a supported file and return text plus tables for analysis."""
    extension = validate_upload(name, data)
    safe_name = _safe_name(name)
    warnings: list[str] = []
    tables: list[pd.DataFrame] = []
    try:
        if extension == ".txt":
            text = data.decode("utf-8-sig", errors="replace").strip()
            if "�" in text:
                warnings.append("Some characters could not be decoded as UTF-8.")
        elif extension == ".csv":
            frame = pd.read_csv(BytesIO(data))
            tables.append(frame)
            text = _table_to_text(frame, safe_name)
        elif extension in {".xlsx", ".xls"}:
            sheets = pd.read_excel(BytesIO(data), sheet_name=None)
            text_parts = []
            for sheet, frame in sheets.items():
                tables.append(frame)
                text_parts.append(_table_to_text(frame, str(sheet)))
            text = "\n\n".join(part for part in text_parts if part)
        else:
            text = _read_pdf(data, warnings)
    except InvalidFileError:
        raise
    except Exception as exc:
        raise InvalidFileError(f"Could not read '{safe_name}': {exc}") from exc
    if not text.strip():
        raise InvalidFileError(
            f"'{safe_name}' contains no readable text. A scanned PDF may need a searchable PDF or Excel/CSV export."
        )
    return DocumentRecord(safe_name, extension, text, safe_name, tables, warnings)


# PDF pages keep their page number so retrieved evidence can be traced back.
def _read_pdf(data: bytes, warnings: list[str]) -> str:
    """Extract selectable text from each PDF page and retain page numbers."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise InvalidFileError(
                "This PDF is password protected. Upload an unlocked copy."
            )
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if page_text:
                pages.append(f"Page {index}\n{page_text}")
        if not pages:
            warnings.append(
                "No selectable text was detected; this may be a scanned PDF."
            )
        return "\n\n".join(pages)
    except InvalidFileError:
        raise
    except Exception as exc:
        raise InvalidFileError(f"The PDF could not be opened: {exc}") from exc
