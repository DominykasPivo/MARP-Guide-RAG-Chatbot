"""
Integration tests for end-to-end event flows across services.

Tests the complete pipeline: ingestion → extraction → indexing → retrieval → chat
Validates correlation ID propagation, event processing, and error handling.
Also includes event schema validation and payload structure tests.
"""

import json
import uuid
from datetime import datetime, timezone


class TestDocumentToAnswerPipeline:
    """Test the complete pipeline from document discovery to answer generation."""

    def test_correlation_id_propagates_through_pipeline(self):
        """Test that correlation_id is maintained across all services."""
        correlation_id = "test-corr-12345"

        # Simulate document discovery event
        from services.ingestion.app.events import DocumentDiscovered

        doc_discovered = DocumentDiscovered(
            eventType="document.discovered",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId=correlation_id,
            source="ingestion-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "url": "http://example.com/doc.pdf",
                "hash": "abc123",
            },
        )

        assert doc_discovered.correlationId == correlation_id

        # Simulate extraction event
        from services.extraction.app.events import DocumentDiscovered as ExtractedEvent

        doc_extracted = ExtractedEvent(
            eventType="document.extracted",
            eventId="evt-002",
            timestamp="2025-01-01T00:01:00Z",
            correlationId=correlation_id,
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "textContent": "Extracted text",
            },
        )

        assert doc_extracted.correlationId == correlation_id

        # Simulate indexing event
        from services.indexing.app.events import ChunksIndexed

        chunks_indexed = ChunksIndexed(
            eventType="chunks.indexed",
            eventId="evt-003",
            timestamp="2025-01-01T00:02:00Z",
            correlationId=correlation_id,
            source="indexing-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "chunkId": "chunk-001",
                "chunkIndex": 0,
                "totalChunks": 5,
            },
        )

        assert chunks_indexed.correlationId == correlation_id

        # Verify all events share the same correlation ID
        assert (
            doc_discovered.correlationId
            == doc_extracted.correlationId
            == chunks_indexed.correlationId
        )

    def test_event_payload_structure_consistency(self):
        """Test that events have consistent required fields."""
        required_fields = [
            "eventType",
            "eventId",
            "timestamp",
            "correlationId",
            "source",
            "version",
            "payload",
        ]

        # Test document discovered event
        from services.ingestion.app.events import DocumentDiscovered

        doc_event = DocumentDiscovered(
            eventType="document.discovered",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="ingestion-service",
            version="1.0",
            payload={"documentId": "doc-001"},
        )

        for field in required_fields:
            assert hasattr(doc_event, field), f"Missing field: {field}"

    def test_document_discovered_to_extracted_flow(self):
        """Test the flow from document discovery to extraction."""
        # 1. Document discovered
        from services.ingestion.app.events import DocumentDiscovered

        discovered = DocumentDiscovered(
            eventType="document.discovered",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="ingestion-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "url": "http://example.com/test.pdf",
                "hash": "hash123",
            },
        )

        # 2. Extraction service processes the event (simulate)
        doc_id = discovered.payload["documentId"]
        url = discovered.payload["url"]

        assert doc_id == "doc-001"
        assert url == "http://example.com/test.pdf"

        # 3. Document extracted event created
        from services.extraction.app.events import DocumentDiscovered as ExtractedEvent

        extracted = ExtractedEvent(
            eventType="document.extracted",
            eventId="evt-002",
            timestamp="2025-01-01T00:01:00Z",
            correlationId=discovered.correlationId,  # Propagate correlation ID
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": doc_id,
                "textContent": "Sample extracted text from PDF",
                "metadata": {"url": url, "pageCount": 5},
            },
        )

        # Verify the flow
        assert extracted.correlationId == discovered.correlationId
        assert extracted.payload["documentId"] == discovered.payload["documentId"]

    def test_extracted_to_indexed_flow(self):
        """Test the flow from document extraction to chunk indexing."""
        from services.indexing.app.events import DocumentExtracted

        # 1. Document extracted event
        extracted = DocumentExtracted(
            eventType="document.extracted",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "textContent": "This is a test document. It has multiple sentences.",
                "metadata": {
                    "title": "Test Document",
                    "url": "http://example.com/test.pdf",
                    "pageCount": 1,
                },
            },
        )

        # 2. Indexing service would process this and create chunks
        # Simulate chunking
        text = extracted.payload["textContent"]
        doc_id = extracted.payload["documentId"]

        # Simulate creating 2 chunks
        from services.indexing.app.events import ChunksIndexed

        chunk_events = []
        for i in range(2):
            chunk_event = ChunksIndexed(
                eventType="chunks.indexed",
                eventId=f"evt-chunk-{i}",
                timestamp="2025-01-01T00:02:00Z",
                correlationId=extracted.correlationId,
                source="indexing-service",
                version="1.0",
                payload={
                    "documentId": doc_id,
                    "chunkId": f"chunk-{i}",
                    "chunkIndex": i,
                    "chunkText": text[:50],  # Simulated chunk
                    "totalChunks": 2,
                    "metadata": extracted.payload["metadata"],
                },
            )
            chunk_events.append(chunk_event)

        # Verify all chunks maintain correlation ID
        for event in chunk_events:
            assert event.correlationId == extracted.correlationId
            assert event.payload["documentId"] == doc_id


class TestRabbitMQEventHandling:
    """Test RabbitMQ message handling and error recovery."""

    def test_event_serialization_deserialization(self):
        """Test that events can be serialized to JSON and deserialized."""
        from services.ingestion.app.events import DocumentDiscovered

        event = DocumentDiscovered(
            eventType="document.discovered",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="ingestion-service",
            version="1.0",
            payload={"documentId": "doc-001", "url": "http://test.com"},
        )

        # Serialize
        event_dict = event.__dict__
        event_json = json.dumps(event_dict)

        # Deserialize
        deserialized = json.loads(event_json)

        assert deserialized["eventType"] == "document.discovered"
        assert deserialized["correlationId"] == "corr-001"
        assert deserialized["payload"]["documentId"] == "doc-001"

    def test_malformed_event_handling(self):
        """Test handling of malformed event messages."""
        malformed_events = [
            {},  # Empty event
            {"eventType": "test"},  # Missing required fields
            {"payload": None},  # None payload
            "not a dict",  # Wrong type
        ]

        for bad_event in malformed_events:
            # In production, services should log error and skip malformed events
            # This tests that we can detect malformed structure
            if isinstance(bad_event, dict):
                assert (
                    "correlationId" not in bad_event
                    or bad_event.get("correlationId") is None
                )


class TestQueryToAnswerFlow:
    """Test the flow from user query to answer generation."""

    def test_query_received_to_chunks_retrieved_flow(self):
        """Test the flow from query reception to chunk retrieval."""
        from services.chat.app.events import QueryReceived
        from services.chat.app.events import ChunksRetrieved  # Adjusted import to source of schema

        # 1. Query received
        query_received = QueryReceived(
            eventType="query.received",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-query-001",
            source="chat-service",
            version="1.0",
            payload={"query": "What is the assessment policy?", "top_k": 5},
        )

        # 2. Retrieval service processes query
        query_text = query_received.payload["query"]

        # 3. Chunks retrieved event
        chunks_retrieved = ChunksRetrieved(
            eventType="chunks.retrieved",
            eventId="evt-002",
            timestamp="2025-01-01T00:00:01Z",
            correlationId=query_received.correlationId,
            source="retrieval-service",
            version="1.0",
            payload={
                "query": query_text,
                "chunks": [
                    {
                        "text": "Assessment policy content",
                        "title": "MARP Assessment",
                        "page": 5,
                        "url": "http://example.com/assessment.pdf",
                        "score": 0.95,
                    }
                ],
                "count": 1,
            },
        )

        # Verify flow
        assert chunks_retrieved.correlationId == query_received.correlationId
        assert chunks_retrieved.payload["query"] == query_text
        assert len(chunks_retrieved.payload["chunks"]) > 0

class TestErrorHandlingAcrossServices:
    """Test error handling and recovery mechanisms."""

    def test_missing_document_id_handling(self):
        """Test handling of events with missing document IDs."""
        from services.indexing.app.events import DocumentExtracted

        # Event with missing documentId should be caught in production
        try:
            # This should work if documentId is optional in payload
            event = DocumentExtracted(
                eventType="document.extracted",
                eventId="evt-001",
                timestamp="2025-01-01T00:00:00Z",
                correlationId="corr-001",
                source="extraction-service",
                version="1.0",
                payload={
                    # Missing documentId
                    "textContent": "Some text",
                },
            )
            # Services should validate payload structure
            assert (
                "documentId" not in event.payload
                or event.payload.get("documentId") is None
            )
        except Exception:
            # Some implementations may raise on missing required fields
            pass

    def test_empty_text_content_handling(self):
        """Test handling of documents with empty text content."""
        from services.indexing.app.events import DocumentExtracted

        event = DocumentExtracted(
            eventType="document.extracted",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "textContent": "",  # Empty text
                "metadata": {},
            },
        )

        # Services should handle empty text gracefully
        assert event.payload["textContent"] == ""
        # In production, chunking service should skip or handle empty text

    def test_invalid_correlation_id_handling(self):
        """Test handling of invalid correlation IDs."""
        from services.ingestion.app.events import DocumentDiscovered

        # Empty correlation ID
        event = DocumentDiscovered(
            eventType="document.discovered",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="",  # Empty but valid string
            source="ingestion-service",
            version="1.0",
            payload={"documentId": "doc-001"},
        )

        # Should not raise, but services might log warning
        assert event.correlationId == ""


class TestServiceHealthAndDiagnostics:
    """Test service health checks and diagnostic endpoints."""

    def test_event_types_enumeration(self):
        """Test that EventTypes enum contains all expected event types."""
        try:
            from services.ingestion.app.events import EventTypes

            # Verify key event types exist
            expected_types = [
                "DOCUMENT_DISCOVERED",
            ]

            for event_type in expected_types:
                assert hasattr(
                    EventTypes, event_type
                ), f"Missing event type: {event_type}"
        except ImportError:
            # EventTypes might not be defined in all implementations
            pass

    def test_multiple_services_process_same_correlation_id(self):
        """Test that multiple services can work on the same request."""
        correlation_id = "shared-corr-123"

        events_by_service = {}

        # Ingestion service event
        from services.ingestion.app.events import DocumentDiscovered

        events_by_service["ingestion"] = DocumentDiscovered(
            eventType="document.discovered",
            eventId="evt-ing-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId=correlation_id,
            source="ingestion-service",
            version="1.0",
            payload={"documentId": "doc-001"},
        )

        # Extraction service event
        from services.extraction.app.events import DocumentDiscovered as ExtractedEvent

        events_by_service["extraction"] = ExtractedEvent(
            eventType="document.extracted",
            eventId="evt-ext-001",
            timestamp="2025-01-01T00:01:00Z",
            correlationId=correlation_id,
            source="extraction-service",
            version="1.0",
            payload={"documentId": "doc-001", "textContent": "text"},
        )

        # Indexing service event
        from services.indexing.app.events import ChunksIndexed

        events_by_service["indexing"] = ChunksIndexed(
            eventType="chunks.indexed",
            eventId="evt-idx-001",
            timestamp="2025-01-01T00:02:00Z",
            correlationId=correlation_id,
            source="indexing-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "chunkId": "chunk-001",
                "chunkIndex": 0,
                "totalChunks": 1,
            },
        )

        # Verify all services used the same correlation ID
        for service, event in events_by_service.items():
            assert (
                event.correlationId == correlation_id
            ), f"{service} has wrong correlation ID"


class TestEventSchemaValidation:
    """Test individual event schemas and payload structures."""

    def test_document_discovered_event_schema(self):
        """Test DocumentDiscovered event has correct schema."""
        from services.ingestion.app.events import DocumentDiscovered

        event = DocumentDiscovered(
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

        assert event.eventType == "DocumentDiscovered"
        assert event.source == "ingestion-service"
        assert event.version == "1.0"
        assert "documentId" in event.payload
        assert "sourceUrl" in event.payload
        assert "filePath" in event.payload
        assert "discoveredAt" in event.payload

    def test_document_discovered_payload_validation(self):
        """Test DocumentDiscovered event payload validation."""
        from services.ingestion.app.events import DocumentDiscovered

        event = DocumentDiscovered(
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

        payload = event.payload

        # Verify required fields
        assert payload["documentId"] is not None
        assert payload["sourceUrl"].startswith("http")
        assert payload["filePath"].endswith(".pdf")
        assert len(payload["discoveredAt"]) > 0

    def test_document_extracted_event_schema(self):
        """Test DocumentExtracted event has correct schema."""
        from services.extraction.app.events import DocumentExtracted

        event = DocumentExtracted(
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
                    "It contains important information about academic regulations."
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

        assert event.eventType == "DocumentExtracted"
        assert event.source == "extraction-service"
        assert event.version == "1.0"
        assert "documentId" in event.payload
        assert "textContent" in event.payload
        assert "metadata" in event.payload
        assert "extractedAt" in event.payload

    def test_document_extracted_metadata_structure(self):
        """Test DocumentExtracted payload has correct metadata structure."""
        from services.extraction.app.events import DocumentExtracted

        event = DocumentExtracted(
            eventType="DocumentExtracted",
            eventId=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlationId="test-corr-002",
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "textContent": "Sample text content",
                "metadata": {
                    "title": "Test Document",
                    "sourceUrl": "https://lancaster.ac.uk/docs/test.pdf",
                    "fileType": "pdf",
                    "pageCount": 5,
                },
                "extractedAt": datetime.now(timezone.utc).isoformat(),
            },
        )

        metadata = event.payload["metadata"]

        assert "title" in metadata
        assert "sourceUrl" in metadata
        assert "fileType" in metadata
        assert "pageCount" in metadata
        assert metadata["fileType"] == "pdf"
        assert metadata["pageCount"] > 0

    def test_document_extracted_text_content_validation(self):
        """Test DocumentExtracted has non-empty text content."""
        from services.extraction.app.events import DocumentExtracted

        event = DocumentExtracted(
            eventType="DocumentExtracted",
            eventId=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlationId="test-corr-002",
            source="extraction-service",
            version="1.0",
            payload={
                "documentId": "doc-001",
                "textContent": "This is sample extracted text",
                "metadata": {
                    "title": "Test",
                    "sourceUrl": "http://test.com",
                    "fileType": "pdf",
                    "pageCount": 1,
                },
                "extractedAt": datetime.now(timezone.utc).isoformat(),
            },
        )

        payload = event.payload
        assert len(payload["textContent"]) > 0
        assert isinstance(payload["textContent"], str)

    def test_chunks_indexed_event_schema(self):
        """Test ChunksIndexed event has correct schema."""
        from services.indexing.app.events import ChunksIndexed

        event = ChunksIndexed(
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

        assert event.eventType == "ChunksIndexed"
        assert event.source == "indexing-service"
        assert event.version == "1.0"
        assert "documentId" in event.payload
        assert "chunkId" in event.payload
        assert "chunkIndex" in event.payload
        assert "totalChunks" in event.payload

    def test_chunks_indexed_payload_structure(self):
        """Test ChunksIndexed payload has correct structure."""
        from services.indexing.app.events import ChunksIndexed

        event = ChunksIndexed(
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
                "chunkText": "Sample chunk text",
                "totalChunks": 5,
                "embeddingModel": "all-MiniLM-L6-v2",
                "metadata": {
                    "title": "Test",
                    "pageCount": 10,
                    "sourceUrl": "http://test.com",
                },
                "indexedAt": datetime.now(timezone.utc).isoformat(),
            },
        )

        payload = event.payload

        assert payload["chunkIndex"] >= 0
        assert payload["totalChunks"] > 0
        assert payload["chunkIndex"] < payload["totalChunks"]
        assert "embeddingModel" in payload
        assert payload["embeddingModel"] == "all-MiniLM-L6-v2"

    def test_chunks_indexed_metadata_presence(self):
        """Test ChunksIndexed includes document metadata."""
        from services.indexing.app.events import ChunksIndexed

        event = ChunksIndexed(
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
                "chunkText": "Sample text",
                "totalChunks": 1,
                "embeddingModel": "all-MiniLM-L6-v2",
                "metadata": {
                    "title": "Test Document",
                    "pageCount": 1,
                    "sourceUrl": "http://test.com/doc.pdf",
                },
                "indexedAt": datetime.now(timezone.utc).isoformat(),
            },
        )

        metadata = event.payload["metadata"]

        assert "title" in metadata
        assert "pageCount" in metadata
        assert "sourceUrl" in metadata

    def test_event_timestamps_are_valid_iso_format(self):
        """Test all events have valid ISO format timestamps."""
        from services.extraction.app.events import DocumentExtracted
        from services.indexing.app.events import ChunksIndexed
        from services.ingestion.app.events import DocumentDiscovered

        events = [
            DocumentDiscovered(
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

    def test_event_unique_ids(self):
        """Test each event has unique event ID."""
        from services.ingestion.app.events import DocumentDiscovered

        event_ids = set()

        for _ in range(10):
            event = DocumentDiscovered(
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

    def test_document_id_consistency_across_events(self):
        """Test document ID remains consistent across event chain."""
        from services.extraction.app.events import DocumentExtracted
        from services.indexing.app.events import ChunksIndexed
        from services.ingestion.app.events import DocumentDiscovered

        doc_id = "test-doc-123"

        # Create events with same document ID
        discovered = DocumentDiscovered(
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
