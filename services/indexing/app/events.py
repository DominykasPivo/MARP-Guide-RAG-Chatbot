# Event types for indexing service
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
import uuid
from datetime import datetime

class EventTypes(Enum):
    """
    Events that the indexing service handles and emits.
    """
    DOCUMENT_EXTRACTED = "document.extracted"  # Consumed from extraction service
    CHUNKS_INDEXED = "chunks.indexed"      # Emitted after successful chunk indexing

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
@dataclass
class ChunksIndexed:
    """Emitted after a document is successfully indexed."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict 
    # def to_dict(self):
    #     return {
    #         "eventType": "ChunksIndexed",
    #         "eventId": str(uuid.uuid4()),
    #         "timestamp": datetime.utcnow().isoformat(),
    #         "correlationId": self.correlation_id,
    #         "source": "indexing-service",
    #         "version": "1.0",
    #         "payload": {
    #             "documentId": self.document_id,
    #             "chunkId": self.chunk_id,
    #             "chunkIndex": self.chunk_index,
    #             "chunkText": self.chunk_text,
    #             "totalChunks": self.total_chunks,
    #             "embeddingModel": self.embedding_model,
    #             "metadata": {
    #                 "title": self.metadata.get("title", "Unknown Title"),
    #                 "pageCount": self.metadata.get("pageCount", 0),
    #                 "sourceUrl": self.metadata.get("sourceUrl", "Unknown Source")
    #             },
    #             "indexedAt": self.indexed_at
    #         }
    #     }
