"""Event schemas and types for extraction."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class EventTypes(Enum):
    """Event types used by extraction."""
    DOCUMENT_DISCOVERED = "document.discovered"
    DOCUMENT_EXTRACTED = "document.extracted"


@dataclass
class DocumentDiscovered:
    """Schema for DocumentDiscovered."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict


@dataclass
class DocumentExtracted:
    """Schema for DocumentExtracted."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict