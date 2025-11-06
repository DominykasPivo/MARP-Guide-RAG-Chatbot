# Event types for ingestion service
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass

class EventTypes(Enum):
    """
    Events that the ingestion service handles and emits.
    """
    DOCUMENT_DISCOVERED = "document.discovered"  # New MARP PDF found

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


# "payload": {
#         "documentId": "string",
#         "title": "string",
#         "pageCount": "integer",
#         "sourceUrl": "string",
#         "filePath": "string",
#         "discoveredAt": "string"
#       }
