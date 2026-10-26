"""Checks for supported document formats and safe upload validation."""

import pytest

from src.documents import read_document
from src.errors import InvalidFileError, UnsupportedFileError


def test_txt_reads_successfully():
    record = read_document("notes.txt", b"Revenue increased in FY2025.")
    assert "Revenue" in record.text


def test_csv_reads_table():
    record = read_document("data.csv", b"Particulars,FY2024,FY2025\nRevenue,100,120\n")
    assert record.tables[0].shape == (1, 3)


def test_unsupported_extension_has_clear_error():
    with pytest.raises(UnsupportedFileError, match="not supported"):
        read_document("notes.docx", b"text")


def test_empty_file_has_clear_error():
    with pytest.raises(InvalidFileError, match="empty"):
        read_document("empty.txt", b"")


def test_invalid_pdf_has_clear_error():
    with pytest.raises(InvalidFileError, match="valid PDF"):
        read_document("bad.pdf", b"not a pdf")
