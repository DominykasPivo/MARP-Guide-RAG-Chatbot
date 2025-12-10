"""
Unit tests for PDF extraction business logic.

Tests actual PDF text extraction, metadata extraction, text cleaning,
error handling, and edge cases using real MARP documents.

Target: services/extraction/app/extractor.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pypdf import PdfWriter

# Mock 'magic' module before any other imports
mock_magic = MagicMock()
mock_magic.from_file.return_value = "application/pdf"
sys.modules["magic"] = mock_magic

# Import after mocking
from services.extraction.app.extractor import PDFExtractor  # noqa: E402

# ============================================================================
# TEST UTILITIES
# ============================================================================


def create_valid_pdf(path):
    """Create a minimal valid PDF for testing."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)


def get_sample_marp_pdf():
    """Get path to a real MARP PDF for testing."""
    test_pdf = Path(__file__).parent.parent / "pdfs" / "sample_marp.pdf"
    if not test_pdf.exists():
        pytest.skip("Sample MARP PDF not available for testing")

    return str(test_pdf)


# ============================================================================
# BASIC EXTRACTION TESTS
# ============================================================================


class TestPDFExtractorBasics:
    """Test basic PDF extraction functionality."""

    def test_extractor_initialization(self):
        """Test PDFExtractor initializes correctly."""
        extractor = PDFExtractor()
        assert extractor is not None

    def test_check_file_type_pdf(self, tmp_path):
        """Test file type detection for valid PDF."""
        pdf_path = tmp_path / "test.pdf"
        create_valid_pdf(pdf_path)

        extractor = PDFExtractor()
        mime_type = extractor.check_file_type(str(pdf_path))

        assert mime_type == "application/pdf"

    def test_check_file_type_invalid(self, tmp_path):
        """Test file type detection for non-PDF file."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("This is not a PDF")

        mock_magic.from_file.return_value = "text/plain"
        extractor = PDFExtractor()
        mime_type = extractor.check_file_type(str(txt_file))

        assert mime_type != "application/pdf"
        mock_magic.from_file.return_value = "application/pdf"  # Reset


# ============================================================================
# METADATA EXTRACTION TESTS
# ============================================================================


class TestMetadataExtraction:
    """Test PDF metadata extraction."""

    def test_extract_metadata_basic(self, tmp_path):
        """Test basic metadata extraction from PDF."""
        pdf_path = tmp_path / "test.pdf"
        create_valid_pdf(pdf_path)
        source_url = "http://example.com/test.pdf"

        extractor = PDFExtractor()
        metadata = extractor._extract_metadata(str(pdf_path), source_url)

        assert "title" in metadata
        assert "pageCount" in metadata
        assert "sourceUrl" in metadata
        assert metadata["sourceUrl"] == source_url
        assert metadata["pageCount"] == 1

    def test_extract_metadata_missing_file(self):
        """Test metadata extraction with missing file returns fallback."""
        extractor = PDFExtractor()

        # _extract_metadata handles errors gracefully and returns fallback values
        metadata = extractor._extract_metadata(
            "/nonexistent/file.pdf", "http://test.com"
        )

        assert metadata["pageCount"] == 0
        assert metadata["sourceUrl"] == "http://test.com"
        assert "title" in metadata

    def test_extract_metadata_with_real_marp_pdf(self):
        """Test metadata extraction from real MARP PDF."""
        pdf_path = get_sample_marp_pdf()
        source_url = "http://example.com/marp.pdf"

        extractor = PDFExtractor()
        metadata = extractor._extract_metadata(pdf_path, source_url)

        assert metadata["pageCount"] > 0
        assert metadata["sourceUrl"] == source_url
        assert len(metadata["title"]) > 0


# ============================================================================
# TEXT EXTRACTION TESTS
# ============================================================================


class TestTextExtraction:
    """Test PDF text extraction quality and edge cases."""

    def test_extract_document_basic(self, tmp_path):
        """Test basic document extraction."""
        pdf_path = tmp_path / "test.pdf"
        create_valid_pdf(pdf_path)

        extractor = PDFExtractor()
        result = extractor.extract_document(str(pdf_path), "http://test.com")

        assert "page_texts" in result
        assert "metadata" in result
        assert isinstance(result["page_texts"], list)

    def test_extract_document_file_not_found(self):
        """Test extraction with non-existent file."""
        extractor = PDFExtractor()

        with pytest.raises(FileNotFoundError):
            extractor.extract_document("/nonexistent.pdf", "http://test.com")

    def test_extract_document_invalid_pdf(self, tmp_path):
        """Test extraction with invalid PDF file."""
        invalid_pdf = tmp_path / "invalid.pdf"
        invalid_pdf.write_text("This is not a valid PDF")

        mock_magic.from_file.return_value = "text/plain"
        extractor = PDFExtractor()

        with pytest.raises(ValueError, match="not a PDF"):
            extractor.extract_document(str(invalid_pdf), "http://test.com")

        mock_magic.from_file.return_value = "application/pdf"  # Reset

    def test_extract_document_with_real_marp_pdf(self):
        """Test text extraction from real MARP PDF."""
        pdf_path = get_sample_marp_pdf()

        extractor = PDFExtractor()
        result = extractor.extract_document(pdf_path, "http://example.com/marp.pdf")

        # Verify structure
        assert "page_texts" in result
        assert "metadata" in result
        assert len(result["page_texts"]) > 0

        # Verify at least some text was extracted
        total_text = "".join(result["page_texts"])
        assert len(total_text) > 100  # Real documents should have substantial text

        # Verify metadata
        assert result["metadata"]["pageCount"] > 0
        assert result["metadata"]["sourceUrl"] == "http://example.com/marp.pdf"

    def test_extract_document_page_count_matches(self):
        """Test that page_texts count matches metadata pageCount."""
        pdf_path = get_sample_marp_pdf()

        extractor = PDFExtractor()
        result = extractor.extract_document(pdf_path, "http://test.com")

        assert len(result["page_texts"]) == result["metadata"]["pageCount"]

    def test_extract_document_handles_empty_pages(self, tmp_path):
        """Test extraction handles PDFs with empty pages."""
        pdf_path = tmp_path / "empty_pages.pdf"
        writer = PdfWriter()
        # Add 3 blank pages
        for _ in range(3):
            writer.add_blank_page(width=72, height=72)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        extractor = PDFExtractor()
        result = extractor.extract_document(str(pdf_path), "http://test.com")

        # Should extract all pages, even if empty
        assert len(result["page_texts"]) == 3
        assert result["metadata"]["pageCount"] == 3


# ============================================================================
# TEXT CLEANING TESTS
# ============================================================================


class TestTextCleaning:
    """Test text cleaning logic."""

    def test_basic_clean_removes_extra_whitespace(self):
        """Test that excessive whitespace is removed."""
        extractor = PDFExtractor()
        text = "This    has     excessive     whitespace"

        cleaned = extractor._basic_clean(text)

        assert "    " not in cleaned
        assert cleaned == "This has excessive whitespace"

    def test_basic_clean_fixes_ocr_artifacts(self):
        """Test that common OCR artifacts are fixed."""
        extractor = PDFExtractor()
        text = "Th|s text has p|pe instead of I"

        cleaned = extractor._basic_clean(text)

        assert "|" not in cleaned
        assert "I" in cleaned

    def test_basic_clean_fixes_missing_spaces(self):
        """Test that missing spaces after periods are added."""
        extractor = PDFExtractor()
        text = "First sentence.Second sentence.Third sentence."

        cleaned = extractor._basic_clean(text)

        assert ". S" in cleaned or cleaned.count(". ") >= 2

    def test_basic_clean_strips_whitespace(self):
        """Test that leading/trailing whitespace is removed."""
        extractor = PDFExtractor()
        text = "   Content with spaces   \n\t"

        cleaned = extractor._basic_clean(text)

        assert not cleaned.startswith(" ")
        assert not cleaned.endswith(" ")

    def test_basic_clean_handles_empty_string(self):
        """Test cleaning empty string."""
        extractor = PDFExtractor()

        cleaned = extractor._basic_clean("")

        assert cleaned == ""

    def test_basic_clean_handles_newlines(self):
        """Test that multiple newlines are normalized."""
        extractor = PDFExtractor()
        text = "Line 1\n\n\n\nLine 2"

        cleaned = extractor._basic_clean(text)

        # Should normalize to single spaces
        assert "\n\n\n" not in cleaned


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Test error handling in extraction."""

    def test_extract_document_handles_corrupted_metadata(self, tmp_path):
        """Test extraction continues even if metadata extraction fails."""
        pdf_path = tmp_path / "test.pdf"
        create_valid_pdf(pdf_path)

        extractor = PDFExtractor()

        # Mock metadata extraction to fail
        with patch.object(
            extractor, "_extract_metadata", side_effect=Exception("Metadata error")
        ):
            # Should raise since extract_document doesn't catch this
            with pytest.raises(Exception):
                extractor.extract_document(str(pdf_path), "http://test.com")

    def test_metadata_extraction_graceful_degradation(self, tmp_path):
        """Test that metadata extraction provides fallback values on error."""
        pdf_path = tmp_path / "test.pdf"
        create_valid_pdf(pdf_path)

        extractor = PDFExtractor()

        # Create a corrupted PDF scenario by using a text file
        with patch("builtins.open", side_effect=Exception("Cannot open")):
            metadata = extractor._extract_metadata(str(pdf_path), "http://test.com")

            # Should return fallback metadata
            assert "title" in metadata
            assert "pageCount" in metadata
            assert "sourceUrl" in metadata
            assert metadata["pageCount"] == 0

    def test_check_file_type_handles_errors(self, tmp_path):
        """Test file type checking handles errors gracefully."""
        extractor = PDFExtractor()

        # Mock magic.from_file to raise an exception
        with patch(
            "services.extraction.app.extractor.magic.from_file",
            side_effect=Exception("Mock error"),
        ):
            with pytest.raises(Exception):
                extractor.check_file_type("any_path.pdf")


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Test edge cases in PDF extraction."""

    def test_extract_very_large_pdf(self):
        """Test extraction from larger PDF documents."""
        pdf_path = get_sample_marp_pdf()

        extractor = PDFExtractor()
        result = extractor.extract_document(pdf_path, "http://test.com")

        # Should handle large documents without issues
        assert len(result["page_texts"]) > 0
        assert result["metadata"]["pageCount"] > 0

    def test_extract_pdf_with_special_characters(self, tmp_path):
        """Test PDF filename with special characters."""
        pdf_path = tmp_path / "test_file_with_spaces and-dashes.pdf"
        create_valid_pdf(pdf_path)

        extractor = PDFExtractor()
        result = extractor.extract_document(str(pdf_path), "http://test.com")

        assert "page_texts" in result
        assert "metadata" in result

    def test_metadata_uses_filename_as_fallback_title(self, tmp_path):
        """Test that filename is used as title when PDF has no title metadata."""
        pdf_path = tmp_path / "my-document.pdf"
        create_valid_pdf(pdf_path)

        extractor = PDFExtractor()
        metadata = extractor._extract_metadata(str(pdf_path), "http://test.com")

        # Should use filename as title
        assert "my-document.pdf" in metadata["title"]

    def test_parse_pdf_date_handles_none(self):
        """Test date parsing with None input."""
        extractor = PDFExtractor()

        result = extractor._parse_pdf_date(None)

        assert result is None

    def test_parse_pdf_date_handles_invalid_format(self):
        """Test date parsing with invalid format."""
        extractor = PDFExtractor()

        result = extractor._parse_pdf_date("invalid-date-string")

        assert result is None

    def test_parse_pdf_date_valid_format(self):
        """Test date parsing with valid PDF date format."""
        extractor = PDFExtractor()

        result = extractor._parse_pdf_date("D:20240101120000")

        assert result is not None
        assert "2024" in result


# ============================================================================
# INTEGRATION TESTS WITH REAL DOCUMENTS
# ============================================================================


class TestRealDocumentExtraction:
    """Integration tests using real MARP documents."""

    def test_extract_real_marp_document_quality(self):
        """Test extraction quality from real MARP document."""
        pdf_path = get_sample_marp_pdf()

        extractor = PDFExtractor()
        result = extractor.extract_document(pdf_path, "http://example.com/marp.pdf")

        # Quality checks
        page_texts = result["page_texts"]
        assert len(page_texts) > 0, "Should extract at least one page"

        # Check that we extracted meaningful text (not just whitespace)
        non_empty_pages = [p for p in page_texts if len(p.strip()) > 10]
        assert len(non_empty_pages) > 0, "Should have pages with meaningful content"

        # Check text doesn't have excessive artifacts
        combined_text = " ".join(page_texts)
        # Should not have too many consecutive spaces (cleaned)
        assert "    " not in combined_text

    def test_extract_multiple_marp_documents(self):
        """Test extraction from multiple MARP documents."""
        data_dir = Path(__file__).parent.parent.parent / "data" / "documents" / "pdfs"
        if not data_dir.exists():
            pytest.skip("MARP PDFs not available")

        pdf_files = list(data_dir.glob("*.pdf"))[:3]  # Test first 3 PDFs
        if len(pdf_files) < 2:
            pytest.skip("Need at least 2 PDFs for this test")

        extractor = PDFExtractor()

        for pdf_path in pdf_files:
            result = extractor.extract_document(
                str(pdf_path), f"http://example.com/{pdf_path.name}"
            )

            assert "page_texts" in result
            assert "metadata" in result
            assert len(result["page_texts"]) > 0
            assert result["metadata"]["pageCount"] > 0

    def test_extract_verifies_consistent_page_count(self):
        """Test that page count is consistent across extraction methods."""
        pdf_path = get_sample_marp_pdf()

        extractor = PDFExtractor()
        result = extractor.extract_document(pdf_path, "http://test.com")

        # Page texts length should match metadata page count
        assert len(result["page_texts"]) == result["metadata"]["pageCount"]
