"""Retrieval service (matched to indexing architecture)."""
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from retriever import get_retriever
from rabbitmq import EventConsumer
from events import publish_event, EventTypes
import chromadb
import logging, sys
from fastapi import FastAPI, Request, Body
from fastapi.responses import JSONResponse
import requests

app = FastAPI(__name__)
logger = logging.getLogger('retrieval')

logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more detail
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout
)


rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')

class RetrievalService:
    def __init__(self, rabbitmq_host: str = 'rabbitmq'):
        self.rabbitmq_host = rabbitmq_host
        self.consumer = None
        self.retriever = None
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", f"amqp://guest:guest@{rabbitmq_host}:5672/")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.collection_name = os.getenv("CHROMA_COLLECTION_NAME", "chunks")
        self.chromadb_path = os.getenv("CHROMADB_PATH", "/app/data/chromadb")
        
        logger.info("RetrievalService initialized")
        logger.info(f"  RabbitMQ URL: {self.rabbitmq_url}")
        logger.info(f"  Model: {self.embedding_model}")
        logger.info(f"  ChromaDB path: {self.chromadb_path}")
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
            consumer.subscribe('QueryReceived', self.handle_query_received)
            logger.info("✅ Subscribed to 'queryreceived'")
        except Exception as e:
            logger.error(f"❌ Failed to subscribe 'QueryReceived': {e}")
        try:
            consumer.subscribe('chunks.indexed', self.handle_chunks_indexed)
            logger.info("✅ Subscribed to 'ChunksIndexed'")
        except Exception as e:
            logger.error(f"❌ Failed to subscribe 'chunksindexed': {e}")
        
        logger.info("Starting RabbitMQ consumer...")
        consumer.start_consuming()

    def handle_chunks_indexed(self, ch, method, properties, body):
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        try:
            event = json.loads(body)
            if event.get('eventType') != 'ChunksIndexed':
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            payload = event.get('payload', {})
            document_id = payload.get('documentId')
            chunk_index = payload.get('chunkIndex', 0)
            total_chunks = payload.get('totalChunks', 1)

            logger.info("📨 ChunksIndexed received", extra={
                "correlation_id": correlation_id,
                "document_id": document_id,
                "chunk_index": f"{chunk_index + 1}/{total_chunks}",
            })

            # Invalidate cache on final chunk (same logic as indexing service pattern)
            if chunk_index == total_chunks - 1:
                retriever = self._ensure_retriever()
                retriever.invalidate_cache()
                logger.info("♻️ Final chunk indexed - cache invalidated", extra={
                    "correlation_id": correlation_id,
                    "document_id": document_id,
                    "total_chunks": total_chunks
                })
            
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError:
            logger.error("Failed to parse ChunksIndexed JSON", extra={"correlation_id": correlation_id}, exc_info=True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"ChunksIndexed handler error: {e}", extra={"correlation_id": correlation_id}, exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def handle_query_received(self, ch, method, properties, body):
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        try:
            event = json.loads(body)
            if event.get('eventType') != 'QueryReceived':
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            payload = event.get('payload', {})
            query_id = payload.get('queryId')
            query_text = payload.get('queryText')
            
            if not query_text:
                logger.error("Missing queryText", extra={"correlation_id": correlation_id})
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            logger.info("📨 Processing QueryReceived", extra={
                "correlation_id": correlation_id,
                "query_id": query_id,
                "query": query_text
            })

            start_time = time.time()
            retriever = self._ensure_retriever()
            chunks = retriever.search(query_text, top_k=5)
            processing_time = (time.time() - start_time) * 1000

            logger.info(f"⏱️ Retrieved {len(chunks)} chunks in {processing_time:.2f}ms", extra={
                "correlation_id": correlation_id,
                "query_id": query_id
            })

            # Publish RetrievalCompleted event
            top_score = chunks[0]['relevanceScore'] if chunks else 0.0
            publish_event("RetrievalCompleted", {
                "queryId": query_id,
                "query": query_text,
                "resultsCount": len(chunks),
                "topScore": float(top_score),
                "latencyMs": int(processing_time)
            }, self.rabbitmq_url)

            # Publish ChunksRetrieved event
            out_payload = {
                "queryId": query_id,
                "retrievedChunks": chunks,
                "retrievalModel": self.embedding_model
            }
            
            if publish_event(EventTypes.CHUNKS_RETRIEVED.value, out_payload, self.rabbitmq_url):
                logger.info("✅ Published ChunksRetrieved", extra={
                    "correlation_id": correlation_id,
                    "query_id": query_id,
                    "chunks_count": len(chunks),
                    "processing_time_ms": processing_time
                })
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                logger.error("❌ Failed to publish ChunksRetrieved", extra={"correlation_id": correlation_id})
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        except json.JSONDecodeError:
            logger.error("Failed to parse QueryReceived JSON", extra={"correlation_id": correlation_id}, exc_info=True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"QueryReceived handler error: {e}", extra={"correlation_id": correlation_id}, exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


@app.get('/')
def home():
    return {"message": "Retrieval Service is running"}

@app.get('/health')
def health():
    """Health check endpoint (matched to indexing service style)."""
    try:
        # Check RabbitMQ
        consumer = service._ensure_consumer()
        rabbitmq_status = "healthy" if consumer.connection and not consumer.connection.is_closed else "unhealthy"

        # Check ChromaDB (same approach as indexing)
        try:
            chromadb_path = os.getenv("CHROMADB_PATH", "/app/data/chromadb")
            client = chromadb.PersistentClient(path=chromadb_path)
            collection_name = os.getenv("CHROMA_COLLECTION_NAME", "chunks")
            collection = client.get_collection(name=collection_name)
            doc_count = collection.count()
            chromadb_status = "healthy"
            logger.info(f"ChromaDB health check passed: {doc_count} documents")
        except Exception as e:
            chromadb_status = "unhealthy"
            doc_count = 0
            logger.error(f"ChromaDB health check failed: {e}")

        # Overall status
        overall_status = "healthy" if rabbitmq_status == "healthy" and chromadb_status == "healthy" else "unhealthy"

        response = {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "retrieval",
            "dependencies": {
                "rabbitmq": rabbitmq_status,
                "chromadb": chromadb_status,
                "documents_count": doc_count
            }
        }
        
        status_code = 200 if overall_status == "healthy" else 503
        return JSONResponse(response, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, status_code=503)
    

@app.get('/debug/vector-store')
def debug_vector_store():
    """Debug endpoint to inspect vector store state."""
    try:
        retriever = service._ensure_retriever()
        if not retriever.collection:
            return JSONResponse({"status": "not_initialized", "error": "Collection not initialized"}, status_code=500)

        count = retriever.collection.count()
        sample_results = []
        
        if count > 0:
            results = retriever.collection.get(limit=5, include=['documents', 'metadatas'])
            for i in range(len(results.get('ids', []))):
                sample_results.append({
                    "id": results['ids'][i],
                    "text_preview": (results['documents'][i] or "")[:120],
                    "metadata": results['metadatas'][i]
                })

        return JSONResponse({
            "status": "healthy" if count > 0 else "empty",
            "collection_name": retriever.collection_name,
            "chromadb_path": retriever.chromadb_path,
            "embedding_model": retriever.embedding_model_name,
            "total_documents": count,
            "sample_documents": sample_results,
            "has_documents": count > 0
        }), 200
        
    except Exception as e:
        logger.error(f"Debug endpoint failed: {e}", exc_info=True)
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.post('/search')
def search(data: dict = Body(...)):
    """Direct search endpoint (bypasses events)."""
    try:
        if not data:
            return JSONResponse({"error": "Request must include JSON data"}, status_code=400)
        query = data.get('query')
        if not isinstance(query, str) or not query.strip():
            return JSONResponse({"error": "Missing required parameter: query"}, status_code=400)
        top_k = data.get('top_k', 5)
        if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
            top_k = 5
        start_time = time.time()
        retriever = service._ensure_retriever()
        chunks = retriever.search(query, top_k)
        processing_time = (time.time() - start_time) * 1000
        correlation_id = str(uuid.uuid4())
        top_score = chunks[0]['relevanceScore'] if chunks else 0.0
        publish_event("RetrievalCompleted", {
            "queryId": correlation_id,
            "query": query,
            "resultsCount": len(chunks),
            "topScore": float(top_score),
            "latencyMs": int(processing_time)
        }, service.rabbitmq_url)
        formatted_results = [{
            "text": c.get('text', ''),
            "metadata": {
                "title": c.get('title', 'MARP Document'),
                "page": c.get('page', 1),
                "url": c.get('url', '')
            },
            "score": c.get('relevanceScore', 0.0)
        } for c in chunks]
        return JSONResponse({"query": query, "results": formatted_results}, status_code=200)
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/query')
def query(data: dict = Body(...)):
    """Alternative query endpoint."""
    try:
        if not data:
            return JSONResponse({"error": "Request must include JSON data"}, status_code=400)
        query_text = data.get('query')
        if not query_text:
            return JSONResponse({"error": "Query is required"}, status_code=400)
        top_k = data.get('top_k', 5)
        start_time = time.time()
        retriever = service._ensure_retriever()
        chunks = retriever.search(query_text, top_k)
        processing_time = (time.time() - start_time) * 1000
        formatted_chunks = [{
            "text": c.get('text', ''),
            "title": c.get('title', 'Unknown'),
            "page": c.get('page', 0),
            "url": c.get('url', '')
        } for c in chunks]
        correlation_id = str(uuid.uuid4())
        logger.info("Query completed", extra={
            "correlation_id": correlation_id,
            "results_count": len(formatted_chunks),
            "processing_time_ms": processing_time
        })
        return JSONResponse({"query": query_text, "chunks": formatted_chunks}, status_code=200)
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
    

def start_consumer():
    retrieval_consumer = EventConsumer(EventTypes.DOCUMENT_EXTRACTED.value, service.start)
    retrieval_consumer.daemon = True
    retrieval_consumer.start()
    logger.info("✅ RabbitMQ consumer thread started")

@app.on_event("startup")
def on_startup():
    start_consumer()
