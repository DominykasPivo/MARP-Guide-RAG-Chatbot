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
    """Event types for the chat service."""

    QUERY_RECEIVED = "queryreceived"
    CHUNKS_RETRIEVED = "chunksretrieved"
    RESPONSE_GENERATED = "responsegenerated"
    ANSWER_GENERATED = "answergenerated"


@dataclass
class QueryReceived:
    """Outgoing event when user submits a query."""

    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict

    # Schema matches Attachment #1:
    # "payload": {
    #     "queryId": "string",
    #     "userId": "string",
    #     "queryText": "string"
    # }


@dataclass
class ChunksRetrieved:
    """Incoming event from retrieval service."""

    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict

    # Schema matches Attachment #2 + SPEC REQUIREMENTS:
    # "payload": {
    #     "queryId": "string",
    #     "retrievedChunks": [
    #         {
    #             "chunkId": "string",
    #             "documentId": "string",
    #             "text": "string",              # ← CRITICAL for RAG
    #             "title": "string",             # ← CRITICAL for citations
    #             "page": "number",              # ← CRITICAL for citations
    #             "url": "string",               # ← CRITICAL for citations
    #             "relevanceScore": "number"
    #         }
    #     ],
    #     "retrievalModel": "string"
    # }


@dataclass
class ResponseGenerated:
    """Outgoing event after generating answer."""

    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict

    # "payload": {
    #     "queryId": "string",
    #     "userId": "string",
    #     "answer": "string",
    #     "citations": [
    #         {
    #             "title": "string",
    #             "page": "number",
    #             "url": "string"
    #         }
    #     ],
    #     "modelUsed": "string",
    #     "retrievalModel": "string"
    # }


@dataclass
class AnswerGenerated:
    """✅ Event after LLM generates answer (matches Attachment #3)."""

    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict

    # Schema matches Attachment #3:
    # "payload": {
    #     "queryId": "string",
    #     "answerText": "string",          # ← Note: Attachment uses
    #                                      #   "answerText"
    #     "citations": [
    #         {
    #             "documentId": "string",
    #             "chunkId": "string",
    #             "sourcePage": "integer"
    #         }
    #     ],
    #     "confidence": "number",
    # }


def publish_event(event_type: str, payload: dict, rabbitmq_url: Optional[str] = None):
    """Publish an event to RabbitMQ.

    Args:
        event_type: Type of event (e.g., "QueryReceived")
        payload: Event payload data
        rabbitmq_url: RabbitMQ connection URL (defaults to env var)
    """
    if rabbitmq_url is None:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    correlation_id = payload.get("queryId", str(uuid.uuid4()))

    try:
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        rabbitmq_url = os.getenv(
            "RABBITMQ_URL", f"amqp://guest:guest@{rabbitmq_host}:5672/"
        )

        # Create connection
        parameters = pika.URLParameters(rabbitmq_url)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
        )

        # Declare exchange
        channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
        )

        # Create event
        event = {
            "eventType": EventTypes.QUERY_RECEIVED.value,
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlationId": correlation_id,
            "source": "chat-service",
            "version": "1.0",
            "payload": payload,
        }

        # Publish event
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


def publish_query_event(
    query: str, correlation_id: str, rabbitmq_url: Optional[str] = None
):
    """Publish a queryreceived event to RabbitMQ (simple version for chat-service)."""
    if rabbitmq_url is None:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    try:
        logger.info("🔌 Publishing query event to RabbitMQ")
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
        )
        event = {
            "query": query,
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).timestamp(),
        }
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key="queryreceived",
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ),
        )

        logger.info(f"📤 Published queryreceived event: {correlation_id}")

        connection.close()

    except Exception as e:
        logger.error(f"❌ Error publishing query event: {str(e)}", exc_info=True)
