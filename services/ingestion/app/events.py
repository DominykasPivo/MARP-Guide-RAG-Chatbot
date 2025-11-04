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
    """Triggered when a new MARP PDF is found for ingestion."""
    document_id: str
    title: str
    source_url: str
    file_path: str
    discovered_at: str
    correlation_id: str  # Required for tracing
    last_modified: Optional[str] = None  # From HTTP headers
    page_count: Optional[int] = None  # Number of pages in the PDF