import json
import uuid
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List
import pika
from logging_config import setup_logger

logger = setup_logger('chat.events')

EXCHANGE_NAME = 'document_events'

class EventTypes(Enum):
    """Event types for the chat service."""
    QUERY_RECEIVED = "QueryReceived"
    CHUNKS_RETRIEVED = "ChunksRetrieved"
    RESPONSE_GENERATED = "ResponseGenerated"
    ANSWER_GENERATED = "AnswerGenerated"  # ← ADDED

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
    #     "answerText": "string",          # ← Note: Attachment uses "answerText"
    #     "citations": [
    #         {
    #             "documentId": "string",
    #             "chunkId": "string",
    #             "sourcePage": "integer"
    #         }
    #     ],
    #     "confidence": "number",
    #     "generatedAt": "string (ISO 8601)"
    # }

def publish_event(event_type: str, payload: dict, rabbitmq_url: str = None):
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
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic', durable=True)

        event = {
            "eventType": event_type,
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlationId": correlation_id,
            "source": "chat-service",
            "version": "1.0",
            "payload": payload
        }

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=event_type.lower(),
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,
                correlation_id=correlation_id
            )
        )
        
        logger.info(f"Published {event_type} event", extra={'correlation_id': correlation_id})
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to publish event: {str(e)}", extra={'correlation_id': correlation_id})
        return False