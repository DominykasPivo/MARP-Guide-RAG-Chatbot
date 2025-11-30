# Explicit field and payload key checks for event schemas (excluding chat events)
def test_document_discovered_fields():
    from services.ingestion.app.events import DocumentDiscovered
    event = DocumentDiscovered(
        eventType="document.discovered",
        eventId="id",
        timestamp="2025-11-27T12:00:00Z",
        correlationId="corr",
        source="ingestion-service",
        version="1.0",
        payload={
            "documentId": "docid",
            "sourceUrl": "url",
            "filePath": "path",
            "discoveredAt": "2025-11-27T12:00:00Z"
        }
    )
    for field in ["eventType", "eventId", "timestamp", "correlationId", "source", "version", "payload"]:
        assert hasattr(event, field)
    for key in ["documentId", "sourceUrl", "filePath", "discoveredAt"]:
        assert key in event.payload

def test_document_extracted_fields():
    from services.indexing.app.events import DocumentExtracted
    event = DocumentExtracted(
        eventType="document.extracted",
        eventId="id",
        timestamp="2025-11-27T12:00:00Z",
        correlationId="corr",
        source="indexing-service",
        version="1.0",
        payload={
            "documentId": "docid",
            "textContent": "text",
            "metadata": {
                "title": "title",
                "sourceUrl": "url",
                "fileType": "pdf",
                "pageCount": 1
            },
            "extractedAt": "2025-11-27T12:00:00Z"
        }
    )
    for field in ["eventType", "eventId", "timestamp", "correlationId", "source", "version", "payload"]:
        assert hasattr(event, field)
    for key in ["documentId", "textContent", "metadata", "extractedAt"]:
        assert key in event.payload
    for meta_key in ["title", "sourceUrl", "fileType", "pageCount"]:
        assert meta_key in event.payload["metadata"]

def test_chunks_indexed_fields():
    from services.indexing.app.events import ChunksIndexed
    event = ChunksIndexed(
        eventType="ChunksIndexed",
        eventId="id",
        timestamp="2025-11-27T12:00:00Z",
        correlationId="corr",
        source="indexing-service",
        version="1.0",
        payload={
            "documentId": "docid",
            "chunkId": "chunkid",
            "chunkIndex": 0,
            "chunkText": "text",
            "totalChunks": 1,
            "embeddingModel": "model",
            "metadata": {
                "title": "title",
                "pageCount": 1,
                "sourceUrl": "url"
            },
            "indexedAt": "2025-11-27T12:00:00Z"
        }
    )
    for field in ["eventType", "eventId", "timestamp", "correlationId", "source", "version", "payload"]:
        assert hasattr(event, field)
    for key in ["documentId", "chunkId", "chunkIndex", "chunkText", "totalChunks", "embeddingModel", "metadata", "indexedAt"]:
        assert key in event.payload
    for meta_key in ["title", "pageCount", "sourceUrl"]:
        assert meta_key in event.payload["metadata"]

import pytest
from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic import ValidationError

# Import only the event dataclasses from each events.py
from services.ingestion.app.events import DocumentDiscovered
from services.retrieval.app.events import QueryReceived, ChunksIndexed, ChunksRetrieved, RetrievalCompleted
from services.indexing.app.events import DocumentExtracted, ChunksIndexed as IndexingChunksIndexed
from services.extraction.app.events import DocumentDiscovered as ExtractionDocumentDiscovered, DocumentExtracted as ExtractionDocumentExtracted
from services.chat.app.events import QueryReceived as ChatQueryReceived, ChunksRetrieved as ChatChunksRetrieved, ResponseGenerated, AnswerGenerated

EVENT_DATACLASSES = [
    DocumentDiscovered,
    QueryReceived,
    ChunksIndexed,
    ChunksRetrieved,
    RetrievalCompleted,
    DocumentExtracted,
    IndexingChunksIndexed,
    ExtractionDocumentDiscovered,
    ExtractionDocumentExtracted,

    
]


# Individual tests for each event dataclass (excluding chat events)
def _test_required_fields(datacls):
    PydanticDataclass = pydantic_dataclass(datacls)
    valid_event = {f: "test" if t == str else {} for f, t in datacls.__annotations__.items()}
    valid_event["payload"] = {}
    # Should not raise
    PydanticDataclass(**valid_event)
    # Test each required field missing
    for field in datacls.__annotations__:
        event = valid_event.copy()
        event.pop(field)
        with pytest.raises(ValidationError):
            PydanticDataclass(**event)

def test_ingestion_document_discovered():
    _test_required_fields(DocumentDiscovered)

def test_retrieval_query_received():
    _test_required_fields(QueryReceived)

def test_retrieval_chunks_indexed():
    _test_required_fields(ChunksIndexed)

def test_retrieval_chunks_retrieved():
    _test_required_fields(ChunksRetrieved)

def test_retrieval_retrieval_completed():
    _test_required_fields(RetrievalCompleted)

def test_indexing_document_extracted():
    _test_required_fields(DocumentExtracted)

def test_indexing_chunks_indexed():
    _test_required_fields(IndexingChunksIndexed)

def test_extraction_document_discovered():
    _test_required_fields(ExtractionDocumentDiscovered)

def test_extraction_document_extracted():
    _test_required_fields(ExtractionDocumentExtracted)
