import sys
from unittest.mock import MagicMock

from pypdf import PdfWriter

from services.extraction.app.extractor import PDFExtractor

# Mock 'magic' module before any other imports
mock_magic = MagicMock()
mock_magic.from_file.return_value = "application/pdf"
sys.modules["magic"] = mock_magic


def create_valid_pdf(path):
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)


def test_pdfextractor_extract_metadata(tmp_path):
    # Create a valid dummy PDF file
    dummy_pdf = tmp_path / "test.pdf"
    create_valid_pdf(dummy_pdf)
    source_url = "http://example.com/test.pdf"
    extractor = PDFExtractor()
    metadata = extractor._extract_metadata(str(dummy_pdf), source_url)
    assert metadata == {
        "title": "test.pdf",
        "pageCount": 1,
        "sourceUrl": source_url,
    }
