# Explicit field and payload key checks for event schemas (excluding chat
# events)
import pytest
from pydantic import ValidationError
from pydantic.dataclasses import dataclass as pydantic_dataclass

from services.extraction.app.events import (
    DocumentDiscovered as ExtractionDocumentDiscovered,
)
from services.indexing.app.events import ChunksIndexed as IndexingChunksIndexed
from services.indexing.app.events import (
    DocumentExtracted,
)
from services.ingestion.app.events import DocumentDiscovered
from services.retrieval.app.retrieval_events import (
    ChunksIndexed,
    ChunksRetrieved,
    QueryReceived,
    RetrievalCompleted,
)

# Import only the event dataclasses from each events.py
EVENT_DATACLASSES = [
    DocumentDiscovered,
    QueryReceived,
    ChunksIndexed,
    ChunksRetrieved,
    RetrievalCompleted,
    DocumentExtracted,
    IndexingChunksIndexed,
    ExtractionDocumentDiscovered,
]


# Individual tests for each event dataclass (excluding chat events)
def _test_required_fields(datacls):
    PydanticDataclass = pydantic_dataclass(datacls)
    valid_event = {
        f: "test" if t == str else {} for f, t in datacls.__annotations__.items()
    }
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
