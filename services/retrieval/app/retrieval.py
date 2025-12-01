import json
import logging
import os
import time
import uuid

from events import EventTypes, publish_event
from rabbitmq import EventConsumer
from retriever import get_retriever

logger = logging.getLogger("retrieval")


class RetrievalService:
    def __init__(self, rabbitmq_host: str = "rabbitmq"):
        self.rabbitmq_host = rabbitmq_host
        self.consumer = None
        self.retriever = None
        self.rabbitmq_url = os.getenv(
            "RABBITMQ_URL", f"amqp://guest:guest@{rabbitmq_host}:5672/"
        )
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", "chunks")
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        logger.info("RetrievalService initialized")
        logger.info(f"  RabbitMQ URL: {self.rabbitmq_url}")
        logger.info(f"  Model: {self.embedding_model}")
        logger.info(f"  Qdrant host: {self.qdrant_host}:{self.qdrant_port}")
        logger.info(f"  Collection: {self.collection_name}")

    def _ensure_consumer(self):
        if self.consumer is None:
            self.consumer = EventConsumer(rabbitmq_host=self.rabbitmq_host)
        return self.consumer

    def _ensure_retriever(self):
        if self.retriever is None:
            logger.info("Initializing retriever...")
            self.retriever = get_retriever()
            logger.info("✅ Retriever initialized")
        return self.retriever

    def start(self):
        logger.info("Starting retrieval service...")
        consumer = self._ensure_consumer()
        try:
            consumer.subscribe("QueryReceived", self.handle_query_received)
            logger.info("✅ Subscribed to 'queryreceived'")
        except Exception as e:
            logger.error(f"❌ Failed to subscribe 'QueryReceived': {e}")
        try:
            consumer.subscribe("chunks.indexed", self.handle_chunks_indexed)
            logger.info("✅ Subscribed to 'ChunksIndexed'")
        except Exception as e:
            logger.error(f"❌ Failed to subscribe 'chunksindexed': {e}")
        logger.info("Starting RabbitMQ consumer...")
        consumer.start_consuming()

    def handle_chunks_indexed(self, ch, method, properties, body):
        correlation_id = (
            properties.correlation_id
            if properties and properties.correlation_id
            else str(uuid.uuid4())
        )
        try:
            event = json.loads(body)
            if event.get("eventType") != "ChunksIndexed":
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            payload = event.get("payload", {})
            document_id = payload.get("documentId")
            chunk_index = payload.get("chunkIndex", 0)
            total_chunks = payload.get("totalChunks", 1)
            logger.info(
                "📨 ChunksIndexed received",
                extra={
                    "correlation_id": correlation_id,
                    "document_id": document_id,
                    "chunk_index": f"{chunk_index + 1}/{total_chunks}",
                },
            )
            if chunk_index == total_chunks - 1:
                retriever = self._ensure_retriever()
                retriever.invalidate_cache()
                logger.info(
                    "♻️ Final chunk indexed - cache invalidated",
                    extra={
                        "correlation_id": correlation_id,
                        "document_id": document_id,
                        "total_chunks": total_chunks,
                    },
                )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse ChunksIndexed JSON",
                extra={"correlation_id": correlation_id},
                exc_info=True,
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(
                f"ChunksIndexed handler error: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True,
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def handle_query_received(self, ch, method, properties, body):
        correlation_id = (
            properties.correlation_id
            if properties and properties.correlation_id
            else str(uuid.uuid4())
        )
        try:
            event = json.loads(body)
            if event.get("eventType") != "QueryReceived":
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            payload = event.get("payload", {})
            query_id = payload.get("queryId")
            query_text = payload.get("queryText")
            if not query_text:
                logger.error(
                    "Missing queryText", extra={"correlation_id": correlation_id}
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            logger.info(
                "📨 Processing QueryReceived",
                extra={
                    "correlation_id": correlation_id,
                    "query_id": query_id,
                    "query": query_text,
                },
            )
            start_time = time.time()
            retriever = self._ensure_retriever()
            chunks = retriever.search(query_text, top_k=5)
            processing_time = (time.time() - start_time) * 1000
            logger.info(
                f"⏱️ Retrieved {
                    len(chunks)} chunks in {
                    processing_time:.2f}ms",
                extra={"correlation_id": correlation_id, "query_id": query_id},
            )
            top_score = chunks[0]["relevanceScore"] if chunks else 0.0
            publish_event(
                "RetrievalCompleted",
                {
                    "queryId": query_id,
                    "query": query_text,
                    "resultsCount": len(chunks),
                    "topScore": float(top_score),
                    "latencyMs": int(processing_time),
                },
                self.rabbitmq_url,
            )
            out_payload = {
                "queryId": query_id,
                "retrievedChunks": chunks,
                "retrievalModel": self.embedding_model,
            }
            if publish_event(
                EventTypes.CHUNKS_RETRIEVED.value, out_payload, self.rabbitmq_url
            ):
                logger.info(
                    "✅ Published ChunksRetrieved",
                    extra={
                        "correlation_id": correlation_id,
                        "query_id": query_id,
                        "chunks_count": len(chunks),
                        "processing_time_ms": processing_time,
                    },
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                logger.error(
                    "❌ Failed to publish ChunksRetrieved",
                    extra={"correlation_id": correlation_id},
                )
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse QueryReceived JSON",
                extra={"correlation_id": correlation_id},
                exc_info=True,
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(
                f"QueryReceived handler error: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True,
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
