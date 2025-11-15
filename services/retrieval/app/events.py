import json
import uuid
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List
import pika
import logging

logger = logging.getLogger('retrieval.events')

EXCHANGE_NAME = 'document_events'

class EventTypes(Enum):
    """Event types for the retrieval service."""
    QUERY_RECEIVED = "QueryReceived"
    CHUNKS_INDEXED = "ChunksIndexed"
    CHUNKS_RETRIEVED = "ChunksRetrieved"
    RETRIEVAL_COMPLETED = "RetrievalCompleted"
    DOCUMENT_EXTRACTED = "DocumentExtracted"

@dataclass
class QueryReceived:
    """Incoming event from chat service."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict

@dataclass
class ChunksIndexed:
    """Incoming event from indexing service."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict

@dataclass
class ChunksRetrieved:
    """Outgoing event after retrieving chunks."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict

@dataclass
class RetrievalCompleted:
    """✅ SPEC REQUIREMENT: Event after search completes."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict
    
    # "payload": {
    #     "queryId": "string",
    #     "query": "string",
    #     "resultsCount": number,
    #     "topScore": number,
    #     "latencyMs": number
    # }

def publish_event(event_type: str, payload: dict, rabbitmq_url: str = None):
    """Publish an event to RabbitMQ.
    
    Args:
        event_type: Type of event (e.g., "ChunksRetrieved")
        payload: Event payload data
        rabbitmq_url: RabbitMQ connection URL (defaults to env var)
    """
    if rabbitmq_url is None:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    
    correlation_id = payload.get("queryId", payload.get("documentId", str(uuid.uuid4())))
    
    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic', durable=True)

        event = {
            "eventType": event_type,
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlationId": correlation_id,
            "source": "retrieval-service",
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