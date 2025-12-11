import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

import pika

logger = logging.getLogger("retrieval.events")

EXCHANGE_NAME = "document_events"


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


def publish_retrieval_completed_event(
    query_id: str,
    query: str,
    results_count: int,
    top_score: float,
    latency_ms: float,
    rabbitmq_url: Optional[str] = None,
):
    """
    Publish RetrievalCompleted event for tracking and observability.
    This will not break retrieval if it fails; it is fire-and-forget.
    """
    if rabbitmq_url is None:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    try:
        logger.info("Publishing RetrievalCompleted event")
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
        )

        event = {
            "eventType": "RetrievalCompleted",
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "retrieval-service",
            "version": "1.0",
            "payload": {
                "queryId": query_id,
                "query": query,
                "resultsCount": results_count,
                "topScore": top_score,
                "latencyMs": latency_ms,
            },
        }

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key="retrievalcompleted",
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2),
        )

        logger.info(f"Published RetrievalCompleted: {query_id}")
        connection.close()

    except Exception as e:
        logger.error(f"Failed to publish RetrievalCompleted event: {e}", exc_info=True)
