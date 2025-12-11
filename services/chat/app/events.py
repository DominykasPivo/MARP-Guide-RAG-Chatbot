import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

import pika

logger = logging.getLogger("chat.events")

EXCHANGE_NAME = "document_events"


class EventTypes(Enum):
    """Event types for chat service."""

    QUERY_RECEIVED = "queryreceived"
    CHUNKS_RETRIEVED = "chunksretrieved"


@dataclass
class QueryReceived:
    """Event schema for QueryReceived."""

    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict


@dataclass
class ChunksRetrieved:
    """Event schema for ChunksRetrieved."""

    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict


def publish_query_received_event(
    query_text: str,
    query_id: str,
    user_id: str = "anonymous",
    rabbitmq_url: Optional[str] = None,
):
    """
    Publish QueryReceived event for tracking and observability.
    Does not impact chat functionality if publishing fails.
    """
    if rabbitmq_url is None:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    try:
        logger.info("Publishing QueryReceived event")
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
        )

        event = {
            "eventType": "QueryReceived",
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "chat-service",
            "version": "1.0",
            "payload": {
                "queryId": query_id,
                "userId": user_id,
                "queryText": query_text,
            },
        }

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key="queryreceived",
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2),
        )

        logger.info(f"Published QueryReceived: {query_id}")
        connection.close()

    except Exception as e:
        logger.error(f"Failed to publish QueryReceived event: {e}", exc_info=True)
