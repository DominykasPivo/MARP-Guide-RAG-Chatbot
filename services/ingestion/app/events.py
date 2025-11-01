# Event types for ingestion service
from enum import Enum
from typing import Dict
from dataclasses import dataclass

class EventTypes(Enum):
    """
    Events that the ingestion service handles and emits.
    """
    DOCUMENT_DISCOVERED = "document.discovered"  # New MARP PDF found
    DOCUMENT_EXTRACTED = "document.extracted"    # Text and metadata extracted

@dataclass
class DocumentDiscovered:
    """Triggered when a new MARP PDF is found for ingestion."""
    document_id: str
    title: str
    source_url: str
    file_path: str
    discovered_at: str
    last_modified: str | None = None
    page_count: int | None = None

@dataclass
class Metadata:
    """Document metadata structure"""
    author: str
    source_url: str
    file_type: str

@dataclass
class DocumentExtracted:
    """Fired after the document text and metadata have been extracted."""
    document_id: str
    title: str
    text_content: str
    page_count: int
    metadata: Metadata
    extracted_at: str