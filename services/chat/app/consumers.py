import json
import logging
import os
import threading

import pika

logger = logging.getLogger("chat.consumers")

EXCHANGE_NAME = "document_events"


def consume_retrieval_completed_events():
    """
    Listen for RetrievalCompleted events for logging and metrics.
    This is for observability only; chat logic remains separate.
    """
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()

        channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
        )

        result = channel.queue_declare(queue="chat_retrieval_tracking", durable=True)
        queue_name = result.method.queue

        channel.queue_bind(
            exchange=EXCHANGE_NAME, queue=queue_name, routing_key="retrievalcompleted"
        )

        def callback(ch, method, properties, body):
            try:
                event = json.loads(body)
                query_id = event.get("payload", {}).get("queryId", "unknown")
                results_count = event.get("payload", {}).get("resultsCount", 0)
                latency_ms = event.get("payload", {}).get("latencyMs", 0)
                top_score = event.get("payload", {}).get("topScore", 0.0)

                logger.info(
                    f"[TRACKING] RetrievalCompleted: queryId={query_id}, "
                    f"results={results_count}, latency={latency_ms}ms, "
                    f"topScore={top_score}"
                )

                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                logger.error(f"Error processing RetrievalCompleted event: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        channel.basic_consume(queue=queue_name, on_message_callback=callback)

        logger.info("Started consuming RetrievalCompleted events (tracking only)")
        channel.start_consuming()

    except Exception as e:
        logger.error(f"Failed to start RetrievalCompleted consumer: {e}", exc_info=True)


def start_consumer_thread():
    """Start event consumer in a background thread."""
    try:
        consumer_thread = threading.Thread(
            target=consume_retrieval_completed_events,
            daemon=True,
        )
        consumer_thread.start()
        logger.info("Event consumer thread started")
    except Exception as e:
        logger.error(f"Failed to start consumer thread: {e}", exc_info=True)
