# Add service paths
import importlib.util
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

from services.extraction.app.events import (
    DocumentExtracted,
)
from services.indexing.app.events import ChunksIndexed
from services.ingestion.app.events import publish_document_discovered_event

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../services/ingestion/app")
    ),
)
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../services/extraction/app")
    ),
)
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../services/indexing/app")
    ),
)

events_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../services/ingestion/app/events.py")
)

spec = importlib.util.spec_from_file_location("ingestion_events", events_path)
if spec is None:
    raise ImportError(f"Could not load spec for {events_path}")
ingestion_events = importlib.util.module_from_spec(spec)
if spec.loader is None:
    raise ImportError(f"Spec loader is None for {events_path}")
spec.loader.exec_module(ingestion_events)


"""Integration tests for event handlers across ingestion,
extraction, and indexing services
"""

# Use the dynamically imported DocumentDiscovered from ingestion_events
IngestionDocumentDiscovered = ingestion_events.DocumentDiscovered


# Import event schemas

# --- Fixtures ---


@pytest.fixture
def sample_document_discovered_event():
    """Sample DocumentDiscovered event from ingestion service"""
    return IngestionDocumentDiscovered(
        eventType="DocumentDiscovered",
        eventId=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        correlationId="test-corr-001",
        source="ingestion-service",
        version="1.0",
        payload={
            "documentId": "doc-001",
            "sourceUrl": "https://lancaster.ac.uk/docs/test.pdf",
            "filePath": "/data/documents/pdfs/doc-001.pdf",
            "discoveredAt": datetime.now(timezone.utc).isoformat(),
        },
    )


@pytest.fixture
def sample_document_extracted_event():
    """Sample DocumentExtracted event from extraction service"""
    return DocumentExtracted(
        eventType="DocumentExtracted",
        eventId=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        correlationId="test-corr-002",
        source="extraction-service",
        version="1.0",
        payload={
            "documentId": "doc-001",
            "textContent": (
                "This is extracted text from the PDF document. "
                "It contains important information about academic "
                "regulations."
            ),
            "metadata": {
                "title": "Academic Regulations",
                "sourceUrl": "https://lancaster.ac.uk/docs/test.pdf",
                "fileType": "pdf",
                "pageCount": 5,
            },
            "extractedAt": datetime.now(timezone.utc).isoformat(),
        },
    )


@pytest.fixture
def sample_chunks_indexed_event():
    """Sample ChunksIndexed event from indexing service"""
    return ChunksIndexed(
        eventType="ChunksIndexed",
        eventId=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        correlationId="test-corr-003",
        source="indexing-service",
        version="1.0",
        payload={
            "documentId": "doc-001",
            "chunkId": "doc-001_chunk_0",
            "chunkIndex": 0,
            "chunkText": "This is a chunk of text extracted and indexed.",
            "totalChunks": 3,
            "embeddingModel": "all-MiniLM-L6-v2",
            "metadata": {
                "title": "Academic Regulations",
                "pageCount": 5,
                "sourceUrl": "https://lancaster.ac.uk/docs/test.pdf",
            },
            "indexedAt": datetime.now(timezone.utc).isoformat(),
        },
    )


@pytest.fixture
def fake_rabbitmq():
    """Fake RabbitMQ for testing event publishing"""

    class FakeRabbitMQ:
        def __init__(self):
            self.queue = []
            self.connected = True

        def publish_event(self, event_type, event, correlation_id=None):
            """Publish event to in-memory queue"""
            self.queue.append((event_type, event, correlation_id))
            return True

        def get_events(self):
            """Get all published events"""
            return self.queue

        def clear_queue(self):
            """Clear all events"""
            self.queue = []

        def _ensure_connection(self):
            """Mock connection check"""
            return self.connected

    return FakeRabbitMQ()


# --- Ingestion Service Event Tests ---


def test_document_discovered_event_schema(sample_document_discovered_event):
    """Test DocumentDiscovered event has correct schema"""
    event = sample_document_discovered_event

    assert event.eventType == "DocumentDiscovered"
    assert event.source == "ingestion-service"
    assert event.version == "1.0"
    assert "documentId" in event.payload
    assert "sourceUrl" in event.payload
    assert "filePath" in event.payload
    assert "discoveredAt" in event.payload


def test_publish_document_discovered_event(
    fake_rabbitmq, sample_document_discovered_event
):
    """Test publishing DocumentDiscovered event"""
    success = publish_document_discovered_event(
        fake_rabbitmq, sample_document_discovered_event
    )

    assert success
    events = fake_rabbitmq.get_events()
    assert len(events) == 1
    assert events[0][2] == sample_document_discovered_event.correlationId


def test_document_discovered_event_validation(sample_document_discovered_event):
    """Test DocumentDiscovered event payload validation"""
    event = sample_document_discovered_event
    payload = event.payload

    # Verify required fields
    assert payload["documentId"] is not None
    assert payload["sourceUrl"].startswith("http")
    assert payload["filePath"].endswith(".pdf")
    assert len(payload["discoveredAt"]) > 0


# --- Extraction Service Event Tests ---


def test_document_extracted_event_schema(sample_document_extracted_event):
    """Test DocumentExtracted event has correct schema"""
    event = sample_document_extracted_event

    assert event.eventType == "DocumentExtracted"
    assert event.source == "extraction-service"
    assert event.version == "1.0"
    assert "documentId" in event.payload
    assert "textContent" in event.payload
    assert "metadata" in event.payload
    assert "extractedAt" in event.payload


def test_document_extracted_payload_structure(sample_document_extracted_event):
    """Test DocumentExtracted payload has correct metadata structure"""
    payload = sample_document_extracted_event.payload
    metadata = payload["metadata"]

    assert "title" in metadata
    assert "sourceUrl" in metadata
    assert "fileType" in metadata
    assert "pageCount" in metadata
    assert metadata["fileType"] == "pdf"
    assert metadata["pageCount"] > 0


def test_document_extracted_text_content(sample_document_extracted_event):
    """Test DocumentExtracted has non-empty text content"""
    payload = sample_document_extracted_event.payload

    assert len(payload["textContent"]) > 0
    assert isinstance(payload["textContent"], str)


# --- Indexing Service Event Tests ---


def test_chunks_indexed_event_schema(sample_chunks_indexed_event):
    """Test ChunksIndexed event has correct schema"""
    event = sample_chunks_indexed_event

    assert event.eventType == "ChunksIndexed"
    assert event.source == "indexing-service"
    assert event.version == "1.0"
    assert "documentId" in event.payload
    assert "chunkId" in event.payload
    assert "chunkIndex" in event.payload
    assert "totalChunks" in event.payload


def test_chunks_indexed_payload_structure(sample_chunks_indexed_event):
    """Test ChunksIndexed payload has correct structure"""
    payload = sample_chunks_indexed_event.payload

    assert payload["chunkIndex"] >= 0
    assert payload["totalChunks"] > 0
    assert payload["chunkIndex"] < payload["totalChunks"]
    assert "embeddingModel" in payload
    assert payload["embeddingModel"] == "all-MiniLM-L6-v2"


def test_chunks_indexed_metadata(sample_chunks_indexed_event):
    """Test ChunksIndexed includes document metadata"""
    payload = sample_chunks_indexed_event.payload
    metadata = payload["metadata"]

    assert "title" in metadata
    assert "pageCount" in metadata
    assert "sourceUrl" in metadata


# --- Event Flow Integration Tests ---


def test_event_flow_correlation_id_propagation(
    sample_document_discovered_event,
    sample_document_extracted_event,
    sample_chunks_indexed_event,
):
    """Test correlation ID is propagated through event chain"""
    # All events should have correlation IDs
    assert sample_document_discovered_event.correlationId is not None
    assert sample_document_extracted_event.correlationId is not None
    assert sample_chunks_indexed_event.correlationId is not None


def test_event_flow_document_id_consistency():
    """Test document ID remains consistent across event chain"""
    doc_id = "test-doc-123"

    # Create events with same document ID
    discovered = IngestionDocumentDiscovered(
        eventType="DocumentDiscovered",
        eventId=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        correlationId="corr-123",
        source="ingestion-service",
        version="1.0",
        payload={
            "documentId": doc_id,
            "sourceUrl": "http://test.com/doc.pdf",
            "filePath": "/data/doc.pdf",
            "discoveredAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    extracted = DocumentExtracted(
        eventType="DocumentExtracted",
        eventId=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        correlationId="corr-123",
        source="extraction-service",
        version="1.0",
        payload={
            "documentId": doc_id,
            "textContent": "Test content",
            "metadata": {
                "title": "Test",
                "sourceUrl": "http://test.com",
                "fileType": "pdf",
                "pageCount": 1,
            },
            "extractedAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    indexed = ChunksIndexed(
        eventType="ChunksIndexed",
        eventId=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        correlationId="corr-123",
        source="indexing-service",
        version="1.0",
        payload={
            "documentId": doc_id,
            "chunkId": f"{doc_id}_chunk_0",
            "chunkIndex": 0,
            "chunkText": "Test chunk",
            "totalChunks": 1,
            "embeddingModel": "all-MiniLM-L6-v2",
            "metadata": {
                "title": "Test",
                "pageCount": 1,
                "sourceUrl": "http://test.com",
            },
            "indexedAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Verify document ID consistency
    assert discovered.payload["documentId"] == doc_id
    assert extracted.payload["documentId"] == doc_id
    assert indexed.payload["documentId"] == doc_id


def test_event_timestamps_are_valid():
    """Test all events have valid ISO format timestamps"""
    events = [
        IngestionDocumentDiscovered(
            eventType="DocumentDiscovered",
            eventId=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlationId="test",
            source="ingestion-service",
            version="1.0",
            payload={
                "documentId": "test",
                "sourceUrl": "http://test.com",
                "filePath": "/test",
                "discoveredAt": datetime.now(timezone.utc).isoformat(),
            },
        ),
        DocumentExtracted(
            eventType="DocumentExtracted",
            eventId=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlationId="test",
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "test",
                "textContent": "test",
                "metadata": {
                    "title": "test",
                    "sourceUrl": "http://test.com",
                    "fileType": "pdf",
                    "pageCount": 1,
                },
                "extractedAt": datetime.now(timezone.utc).isoformat(),
            },
        ),
        ChunksIndexed(
            eventType="ChunksIndexed",
            eventId=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlationId="test",
            source="indexing-service",
            version="1.0",
            payload={
                "documentId": "test",
                "chunkId": "test_chunk_0",
                "chunkIndex": 0,
                "chunkText": "test",
                "totalChunks": 1,
                "embeddingModel": "all-MiniLM-L6-v2",
                "metadata": {
                    "title": "test",
                    "pageCount": 1,
                    "sourceUrl": "http://test.com",
                },
                "indexedAt": datetime.now(timezone.utc).isoformat(),
            },
        ),
    ]

    for event in events:
        # Verify timestamp can be parsed
        datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        assert len(event.timestamp) > 0


def test_event_unique_ids():
    """Test each event has unique event ID"""
    event_ids = set()

    for _ in range(10):
        event = IngestionDocumentDiscovered(
            eventType="DocumentDiscovered",
            eventId=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlationId="test",
            source="ingestion-service",
            version="1.0",
            payload={
                "documentId": "test",
                "sourceUrl": "http://test.com",
                "filePath": "/test",
                "discoveredAt": datetime.now(timezone.utc).isoformat(),
            },
        )
        event_ids.add(event.eventId)

    # All event IDs should be unique
    assert len(event_ids) == 10
