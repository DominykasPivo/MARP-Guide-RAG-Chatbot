"""Event schemas and types for the extraction service."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict

class EventTypes(Enum):
    """Event types for document processing."""
    DOCUMENT_DISCOVERED = "document.discovered"  # Incoming event from ingestion service
    DOCUMENT_EXTRACTED = "document.extracted"  # After successful text extraction

@dataclass
class DocumentDiscovered:
    """Event schema for DocumentDiscovered."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict


@dataclass
class DocumentExtracted:
    """Event data for an extracted document."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict 

    # "payload": {
    #     "documentId": "string",
    #     "textContent": "string",
    #     "metadata": {
    #       "title": "string",
    #       "sourceUrl": "string",
    #       "fileType": "string",
    #       "pageCount": "integer"
    #     },
    #     "extractedAt": "string"
    #   }