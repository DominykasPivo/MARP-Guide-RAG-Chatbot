import json
import logging
import os
import threading
import time

import pika

logger = logging.getLogger("retrieval.consumers")

EXCHANGE_NAME = "document_events"

# Metrics tracking
chunks_indexed_count = 0
documents_indexed_count = 0
last_indexed_timestamp = None


def consume_query_received_events():
    """
    Listen for QueryReceived events for logging and metrics.
    Retrieval continues to use HTTP.
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

                logger.info(
                    f"[TRACKING] QueryReceived: queryId={query_id}, "
                    f"userId={user_id}, query='{query_text}'"
                )

                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as exc:
                logger.error(f"Error processing QueryReceived event: {exc}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        channel.basic_consume(queue=queue_name, on_message_callback=callback)

        logger.info("Started consuming QueryReceived events (tracking only)")
        channel.start_consuming()

    except Exception as exc:
        logger.error(f"Failed to start QueryReceived consumer: {exc}", exc_info=True)


def consume_chunks_indexed_events():
    """
    Listen for ChunksIndexed events for logging and metrics tracking.
    This complements the cache invalidation logic in retrieval.py.
    """
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()

        channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
        )

        result = channel.queue_declare(
            queue="retrieval_chunks_indexed_metrics", durable=True
        )
        queue_name = result.method.queue

        channel.queue_bind(
            exchange=EXCHANGE_NAME, queue=queue_name, routing_key="chunks.indexed"
        )

        def callback(ch, method, properties, body):
            global chunks_indexed_count, documents_indexed_count
            global last_indexed_timestamp

            try:
                start_time = time.time()
                event = json.loads(body)

                # Validate event type
                event_type = event.get("eventType")
                if event_type != "ChunksIndexed":
                    logger.warning(f"Unexpected event type: {event_type}")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return

                correlation_id = event.get(
                    "correlationId",
                    properties.correlation_id if properties else "unknown",
                )
                payload = event.get("payload", {})

                document_id = payload.get("documentId", "unknown")
                chunk_id = payload.get("chunkId", "unknown")
                chunk_index = payload.get("chunkIndex", 0)
                total_chunks = payload.get("totalChunks", 1)
                embedding_model = payload.get("embeddingModel", "unknown")
                indexed_at = payload.get("indexedAt", "unknown")

                # Extract metadata
                chunk_metadata = payload.get("metadata", {})
                title = chunk_metadata.get("title", "Unknown Title")
                page_count = chunk_metadata.get("pageCount", 0)
                source_url = chunk_metadata.get("sourceUrl", "Unknown Source")

                # Update metrics
                chunks_indexed_count += 1
                last_indexed_timestamp = time.time()

                # Track document completion
                if chunk_index == total_chunks - 1:
                    documents_indexed_count += 1

                processing_time_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"[METRICS] ChunksIndexed: documentId={document_id}, "
                    f"chunk={chunk_index + 1}/{total_chunks}, "
                    f"chunkId={chunk_id}, "
                    f"title='{title}', "
                    f"model={embedding_model}, "
                    f"indexedAt={indexed_at}, "
                    f"processingTime={processing_time_ms:.2f}ms, "
                    f"totalChunksProcessed={chunks_indexed_count}, "
                    f"totalDocumentsCompleted={documents_indexed_count}",
                    extra={
                        "correlation_id": correlation_id,
                        "document_id": document_id,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "total_chunks": total_chunks,
                        "is_final_chunk": chunk_index == total_chunks - 1,
                        "title": title,
                        "page_count": page_count,
                        "source_url": source_url,
                    },
                )

                # Log document completion milestone
                if chunk_index == total_chunks - 1:
                    logger.info(
                        f"[MILESTONE] Document n\
                        indexing completed: documentId={document_id}, "
                        f"title='{title}', "
                        f"totalChunks={total_chunks}, "
                        f"totalDocumentsIndexed={documents_indexed_count}",
                        extra={
                            "correlation_id": correlation_id,
                            "document_id": document_id,
                            "total_chunks": total_chunks,
                            "title": title,
                        },
                    )

                logger.info(
                    f"Processed chunk indexed event: " f"{chunk_id} for {document_id}"
                )

                ch.basic_ack(delivery_tag=method.delivery_tag)

            except json.JSONDecodeError as exc:
                logger.error(
                    f"Failed to parse ChunksIndexed JSON: {exc}",
                    extra={
                        "correlation_id": (
                            correlation_id
                            if "correlation_id" in locals()
                            else "unknown"
                        )
                    },
                    exc_info=True,
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as exc:
                logger.error(
                    f"Error processing ChunksIndexed event: {exc}",
                    extra={
                        "correlation_id": (
                            correlation_id
                            if "correlation_id" in locals()
                            else "unknown"
                        )
                    },
                    exc_info=True,
                )
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        channel.basic_consume(queue=queue_name, on_message_callback=callback)

        logger.info("Started consuming ChunksIndexed events (metrics and logging)")
        channel.start_consuming()

    except Exception as exc:
        logger.error(f"Failed to start ChunksIndexed consumer: {exc}", exc_info=True)


def _handle_document_indexed_event(body: bytes):
    """Handle document indexed event."""
    try:
        body_dict = json.loads(body.decode("utf-8"))
        logger.info(f"Received document indexed event: {body_dict}")
    except Exception as e:
        logger.error(
            f"Error handling document indexed event: {str(e)}",
            exc_info=True,
        )


def start_consumer_thread():
    """Start event consumer in a background thread."""
    try:
        # Start QueryReceived consumer
        consumer_thread = threading.Thread(
            target=consume_query_received_events, daemon=True
        )
        consumer_thread.start()
        logger.info("QueryReceived consumer thread started")

        # Start ChunksIndexed consumer
        chunks_consumer_thread = threading.Thread(
            target=consume_chunks_indexed_events, daemon=True
        )
        chunks_consumer_thread.start()
        logger.info("ChunksIndexed consumer thread started")

    except Exception as exc:
        logger.error(f"Failed to start consumer thread: {exc}", exc_info=True)


def get_metrics():
    """Return current metrics for monitoring."""
    return {
        "chunks_indexed_total": chunks_indexed_count,
        "documents_indexed_total": documents_indexed_count,
        "last_indexed_timestamp": last_indexed_timestamp,
    }
