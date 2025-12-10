import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import pika

logger = logging.getLogger("retrieval.events")

EXCHANGE_NAME = "document_events"


def publish_retrieval_completed_event(
    query_id: str,
    query: str,
    results_count: int,
    top_score: float,
    latency_ms: float,
    rabbitmq_url: Optional[str] = None,
):
    """
    Publish RetrievalCompleted event for tracking/observability.
    ⚠️ SAFE: This will NOT break retrieval if it fails - it's fire-and-forget.

    Schema matches event catalogue:
    {
      "eventType": "RetrievalCompleted",
      "eventId": "string",
      "timestamp": "string",
      "source": "retrieval-service",
      "version": "1.0",
      "payload": {
        "queryId": "string",
        "query": "string",
        "resultsCount": "integer",
        "topScore": "number",
        "latencyMs": "number"
      }
    }
    """
    if rabbitmq_url is None:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    try:
        logger.info("📤 Publishing RetrievalCompleted event")
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

        logger.info(f"✅ Published RetrievalCompleted: {query_id}")
        connection.close()

    except Exception as e:
        # ⚠️ CRITICAL: We catch and log, but DON'T raise
        logger.error(
            f"❌ Failed to publish RetrievalCompleted event: {e}", exc_info=True
        )
