# Event types for ingestion service
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict

logger = logging.getLogger("ingestion.events")


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
#         "sourceUrl": "string",
#         "filePath": "string",
#         "discoveredAt": "string"
#       }


def publish_document_discovered_event(event_publisher, doc_info: DocumentDiscovered):
    """Publish a DocumentDiscovered event to RabbitMQ using EventPublisher."""
    correlation_id = doc_info.correlationId
    result = event_publisher.publish_event(
        EventTypes.DOCUMENT_DISCOVERED, doc_info, correlation_id=correlation_id
    )
    if result:
        logger.info(
            "Published document discovery event for %s",
            doc_info.payload["documentId"],
            extra={"correlation_id": correlation_id},
        )
    else:
        logger.error(
            "Failed to publish DocumentDiscovered event for %s",
            doc_info.payload["documentId"],
            extra={"correlation_id": correlation_id},
        )
    return result
