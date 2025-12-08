import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

import pika

logger = logging.getLogger("retrieval.events")

EXCHANGE_NAME = "document_events"


class EventTypes(Enum):
    """Event types for the retrieval service."""

    QUERY_RECEIVED = "QueryReceived"
    CHUNKS_INDEXED = "ChunksIndexed"
    CHUNKS_RETRIEVED = "ChunksRetrieved"
    RETRIEVAL_COMPLETED = "RetrievalCompleted"
    DOCUMENT_EXTRACTED = "DocumentExtracted"


@dataclass
class QueryReceived:
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict


@dataclass
class ChunksIndexed:
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict


@dataclass
class ChunksRetrieved:
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict


@dataclass
class RetrievalCompleted:
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict


def publish_event(event_type: str, payload: dict, rabbitmq_url: Optional[str] = None):
    if rabbitmq_url is None:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    correlation_id = payload.get(
        "queryId", payload.get("documentId", str(uuid.uuid4()))
    )
    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
        )
        event = {
            "eventType": event_type,
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlationId": correlation_id,
            "source": "retrieval-service",
            "version": "1.0",
            "payload": payload,
        }
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=event_type.lower(),
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2, correlation_id=correlation_id
            ),
        )
        logger.info(
            f"Published {event_type} event", extra={"correlation_id": correlation_id}
        )
        connection.close()
        return True
    except Exception as e:
        logger.error(
            f"Failed to publish event: {str(e)}",
            extra={"correlation_id": correlation_id},
        )
        return False
