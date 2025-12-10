import json
import logging
import os
import threading

import pika

logger = logging.getLogger("retrieval.consumers")

EXCHANGE_NAME = "document_events"


def consume_query_received_events():
    """
    Listen for QueryReceived events for logging/metrics.
    ⚠️ This is ONLY for observability - retrieval still uses HTTP.
    """
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()

        channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
        )

        result = channel.queue_declare(queue="retrieval_query_tracking", durable=True)
        queue_name = result.method.queue

        channel.queue_bind(
            exchange=EXCHANGE_NAME, queue=queue_name, routing_key="queryreceived"
        )

        def callback(ch, method, properties, body):
            try:
                event = json.loads(body)
                query_id = event.get("payload", {}).get("queryId", "unknown")
                query_text = event.get("payload", {}).get("queryText", "")
                user_id = event.get("payload", {}).get("userId", "unknown")

                # Just log it - HTTP still handles the actual retrieval
                logger.info(
                    f"📊 [TRACKING] QueryReceived: queryId={query_id}, "
                    f"userId={user_id}, query='{query_text}'"
                )

                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                logger.error(f"❌ Error processing QueryReceived event: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        channel.basic_consume(queue=queue_name, on_message_callback=callback)

        logger.info("🎧 Started consuming QueryReceived events (tracking only)")
        channel.start_consuming()

    except Exception as e:
        logger.error(f"❌ Failed to start QueryReceived consumer: {e}", exc_info=True)


def start_consumer_thread():
    """Start event consumer in background thread"""
    try:
        consumer_thread = threading.Thread(
            target=consume_query_received_events, daemon=True
        )
        consumer_thread.start()
        logger.info("✅ Event consumer thread started")
    except Exception as e:
        logger.error(f"❌ Failed to start consumer thread: {e}", exc_info=True)
