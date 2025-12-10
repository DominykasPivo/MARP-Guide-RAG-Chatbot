import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict

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


def publish_query_event(query: str, correlation_id: str):
    """Publish a queryreceived event to RabbitMQ."""
    try:
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        rabbitmq_url = os.getenv(
            "RABBITMQ_URL", f"amqp://guest:guest@{rabbitmq_host}:5672/"
        )

        # Create connection
        parameters = pika.URLParameters(rabbitmq_url)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

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
            "payload": {
                "queryId": correlation_id,
                "userId": "anonymous",
                "queryText": query,
            },
        }

        # Publish event
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key="query.received",
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type="application/json",
            ),
        )

        logger.info(f"📤 Published queryreceived event: {correlation_id}")

        connection.close()

    except Exception as e:
        logger.error(f"❌ Failed to publish query event: {str(e)}", exc_info=True)
