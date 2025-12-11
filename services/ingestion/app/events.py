"""Event models and utilities for the ingestion service."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict

logger = logging.getLogger("ingestion.events")


class EventTypes(Enum):
    """Event types emitted by the ingestion service."""
    DOCUMENT_DISCOVERED = "document.discovered"


@dataclass
class DocumentDiscovered:
    """Schema for document discovery events."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict


def publish_document_discovered_event(event_publisher, doc_info: DocumentDiscovered) -> bool:
    """Publish a DocumentDiscovered event via the event publisher."""
    correlation_id = doc_info.correlationId
    result = event_publisher.publish_event(EventTypes.DOCUMENT_DISCOVERED, doc_info, correlation_id=correlation_id)
    if result:
        logger.info(
            "Document discovery event published.",
            extra={"correlation_id": correlation_id, "document_id": doc_info.payload.get("documentId")},
        )
    else:
        logger.error(
            "Failed to publish document discovery event.",
            extra={"correlation_id": correlation_id, "document_id": doc_info.payload.get("documentId")},
        )
    return result