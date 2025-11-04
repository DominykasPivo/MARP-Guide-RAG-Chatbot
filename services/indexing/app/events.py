# Event types for indexing service
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass

class EventTypes(Enum):
    """
    Events that the indexing service handles and emits.
    """
    DOCUMENT_EXTRACTED = "document.extracted"  # Consumed from extraction service
    CHUNKS_INDEXED = "chunks.indexed"      # Emitted after successful chunk indexing

@dataclass
class DocumentExtracted:
    """Triggered when a document has been extracted and is ready for indexing."""
    document_id: str
    title: str
    page_texts: list  # List of text blocks (one per page or chunk)
    metadata: Dict    # Metadata dictionary (author, source_url, etc.)
    correlation_id: str
    extracted_at: str

@dataclass
class ChunksIndexed:
    """Emitted after a document is successfully indexed."""
    document_id: str
    title: str
    chunk_count: int
    correlation_id: str
    indexed_at: str
