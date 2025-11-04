"""Event schemas and types for the extraction service."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

class EventTypes(Enum):
    """Event types for document processing."""
    DOCUMENT_DISCOVERED = "document.discovered"  # Incoming event from ingestion service
    DOCUMENT_EXTRACTED = "document.extracted"  # After successful text extraction

@dataclass
class DocumentDiscovered:
    """Event data for discovered documents (consumed from ingestion service)."""
    document_id: str
    title: str
    source_url: str
    file_path: str
    discovered_at: str
    correlation_id: str  # Required for tracing
    last_modified: Optional[str] = None  # From HTTP headers
    page_count: Optional[int] = None  # Number of pages in the PDF

@dataclass
class Metadata:
    """Document metadata from extraction."""
    author: str
    source_url: str
    file_type: str
    creation_date: Optional[str]
    last_modified: Optional[str]

@dataclass
class DocumentExtracted:
    """Event data for an extracted document."""
    document_id: str
    title: str
    text_content: str  # Raw extracted text, basic cleaning only
    page_count: int
    correlation_id: str  # For traceability, matches DocumentDiscovered
    metadata: Metadata
    extracted_at: str