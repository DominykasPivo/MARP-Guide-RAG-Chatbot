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


# ============ Additional Extraction Service Tests ============


class TestPDFExtractorBasics:
    """Test basic PDF extraction functionality."""

    def test_pdf_extractor_initialization(self):
        """Test PDFExtractor initialization."""
        extractor = PDFExtractor()
        assert extractor is not None


class TestExtractionEvents:
    """Test extraction service events."""

    def test_document_discovered_event_creation(self):
        """Test creating DocumentDiscovered event."""
        from services.extraction.app.events import DocumentDiscovered

        event = DocumentDiscovered(
            eventType="document.discovered",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="ingestion-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "sourceUrl": "http://example.com/doc.pdf",
                "filePath": "/data/doc.pdf",
                "discoveredAt": "2025-01-01T00:00:00Z",
            },
        )

        assert event.eventType == "document.discovered"
        assert event.payload["documentId"] == "doc-001"
        assert event.correlationId == "corr-001"

    def test_document_extracted_event_creation(self):
        """Test creating DocumentExtracted event."""
        from services.extraction.app.events import DocumentExtracted

        event = DocumentExtracted(
            eventType="document.extracted",
            eventId="evt-002",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "textContent": "This is extracted text from the PDF.",
                "metadata": {
                    "title": "Test Document",
                    "sourceUrl": "http://example.com/doc.pdf",
                    "fileType": "pdf",
                    "pageCount": 5,
                },
                "extractedAt": "2025-01-01T00:00:01Z",
            },
        )

        assert event.eventType == "document.extracted"
        assert "textContent" in event.payload
        assert event.payload["textContent"] == "This is extracted text from the PDF."

    def test_document_extracted_with_long_content(self):
        """Test DocumentExtracted event with long text content."""
        from services.extraction.app.events import DocumentExtracted

        long_text = "This is a long document. " * 1000
        event = DocumentExtracted(
            eventType="document.extracted",
            eventId="evt-003",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "doc-002",
                "textContent": long_text,
                "metadata": {
                    "title": "Long Document",
                    "sourceUrl": "http://example.com/long.pdf",
                    "fileType": "pdf",
                    "pageCount": 100,
                },
            },
        )

        assert len(event.payload["textContent"]) > 5000
        assert event.payload["metadata"]["pageCount"] == 100


class TestExtractionEventTypes:
    """Test event type enumeration."""

    def test_event_types_enum(self):
        """Test EventTypes enumeration."""
        from services.extraction.app.events import EventTypes

        assert EventTypes.DOCUMENT_DISCOVERED.value == "document.discovered"
        assert EventTypes.DOCUMENT_EXTRACTED.value == "document.extracted"


class TestDocumentMetadata:
    """Test document metadata handling in extracted events."""

    def test_metadata_preservation(self):
        """Test that metadata is properly preserved in events."""
        from services.extraction.app.events import DocumentExtracted

        metadata = {
            "title": "Test Title",
            "sourceUrl": "http://example.com/test.pdf",
            "fileType": "pdf",
            "pageCount": 42,
        }

        event = DocumentExtracted(
            eventType="document.extracted",
            eventId="evt-004",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "doc-003",
                "textContent": "Sample text",
                "metadata": metadata,
            },
        )

        assert event.payload["metadata"] == metadata
        assert event.payload["metadata"]["title"] == "Test Title"
        assert event.payload["metadata"]["pageCount"] == 42


class TestCorrelationIDHandling:
    """Test correlation ID handling in extraction events."""

    def test_correlation_id_propagation_discovered(self):
        """Test correlation ID in DocumentDiscovered event."""
        from services.extraction.app.events import DocumentDiscovered

        correlation_id = "test-corr-12345"
        event = DocumentDiscovered(
            eventType="document.discovered",
            eventId="evt-006",
            timestamp="2025-01-01T00:00:00Z",
            correlationId=correlation_id,
            source="ingestion-service",
            version="1.0",
            payload={"documentId": "doc-005"},
        )

        assert event.correlationId == correlation_id

    def test_correlation_id_propagation_extracted(self):
        """Test correlation ID in DocumentExtracted event."""
        from services.extraction.app.events import DocumentExtracted

        correlation_id = "test-corr-67890"
        event = DocumentExtracted(
            eventType="document.extracted",
            eventId="evt-007",
            timestamp="2025-01-01T00:00:00Z",
            correlationId=correlation_id,
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "doc-006",
                "textContent": "Extracted",
                "metadata": {},
            },
        )

        assert event.correlationId == correlation_id


class TestEventDataStructure:
    """Test the structure of event data."""

    def test_event_has_required_fields(self):
        """Test that events have all required fields."""
        from services.extraction.app.events import DocumentExtracted

        event = DocumentExtracted(
            eventType="document.extracted",
            eventId="evt-008",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="extraction-service",
            version="1.0",
            payload={"documentId": "doc-007", "textContent": "Text", "metadata": {}},
        )

        assert hasattr(event, "eventType")
        assert hasattr(event, "eventId")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "correlationId")
        assert hasattr(event, "source")
        assert hasattr(event, "version")
        assert hasattr(event, "payload")

    def test_event_version_tracking(self):
        """Test that event version is properly set."""
        from services.extraction.app.events import DocumentExtracted

        event = DocumentExtracted(
            eventType="document.extracted",
            eventId="evt-009",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="extraction-service",
            version="1.0",
            payload={"documentId": "doc-008", "textContent": "Text", "metadata": {}},
        )

        assert event.version == "1.0"
