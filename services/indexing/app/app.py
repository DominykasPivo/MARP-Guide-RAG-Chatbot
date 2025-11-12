from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from rabbitmq import QUEUE_NAME, ROUTING_KEY, EventConsumer
from semantic_chunking import chunk_document
from embed_chunks import embed_chunks
from threading import Thread
from chromadb_store import store_chunks_in_chromadb
from events import EventTypes
import chromadb
import requests
from rabbitmq import pika,EXCHANGE_NAME
from tenacity import retry, stop_after_attempt, wait_exponential
import json, uuid
from datetime import datetime
import logging
import os


EVENT_VERSION = os.getenv("EVENT_VERSION", "1.0")
chromadb_path = "/data/chromadb"

logger = logging.getLogger('indexing')
logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more detail
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout
)

app = FastAPI(title="MARP Indexing Service", version="1.0.0")


@app.get('/index/status/{doc_id}')
async def index_status(doc_id: str):
    try:
        client = chromadb.PersistentClient(path=chromadb_path)
        collection = client.get_or_create_collection(name="chunks")
        results = collection.get(where={"document_id": {"$eq": doc_id}})
        if results and results.get('ids'):
            logger.debug(f"Returning status for doc_id {doc_id}: indexed, chunk_count={len(results['ids'])}")
            return JSONResponse(content={"indexed": True, "chunk_count": len(results['ids'])}, status_code=200)
        else:
            logger.warning(f"Status requested for unknown or unindexed doc_id: {doc_id}")
            return JSONResponse(content={"indexed": False}, status_code=404)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Error in /index/status/{doc_id}: {e}\nTraceback:\n{tb}")
        return JSONResponse(content={"error": str(e), "traceback": tb}, status_code=500)
    

@app.get('/health')
async def health():
    status = {"service": "indexing"}
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host="rabbitmq"))
        connection.close()
        status["rabbitmq"] = "healthy"
    except Exception as e:
        logger.error(f"RabbitMQ health check failed: {e}")
        status["rabbitmq"] = "unhealthy"
    try:
        client = chromadb.PersistentClient(path=chromadb_path)
        collections = client.list_collections()
        status["chromadb"] = "healthy"
    except Exception as e:
        logger.error(f"ChromaDB health check failed: {e}")
        status["chromadb"] = f"unhealthy ({str(e)})"
    status["status"] = "healthy" if all(v == "healthy" for k, v in status.items() if k != "service") else "unhealthy"
    return JSONResponse(content=status, status_code=200 if status["status"] == "healthy" else 503)


@app.post('/index')
async def index(request: Request):
    """Index a document (requires a DocumentExtracted event payload)
        Args:
        > payload{extractedAt, metadata{title, sourceUrl, fileType, pageCount}, textContent, documentId}, version,
        > source, correlationId, timestamp, eventId, eventType

        Example terminal command to test the /index endpoint:
         >curl -X POST http://localhost:8003/index -H "Content-Type: application/json" -d "{\"eventType\":\"DocumentExtracted\",\"eventId\":\"test-id\",\"timestamp\":\"2025-11-06T12:00:00Z\",\"correlationId\":\"test-corr-id\",\"source\":\"test\",\"version\":\"1.0\",\"payload\":{\"documentId\":\"test-doc-1\",\"textContent\":\"This is a test document for direct indexing.\",\"metadata\":{\"title\":\"Test Doc\",\"sourceUrl\":\"http://example.com\",\"fileType\":\"txt\",\"pageCount\":1},\"extractedAt\":\"2025-11-06T12:00:00Z\"}}"
    
    """
    data = await request.json()
    try:
        process_extracted_event({"data": data})
        return JSONResponse(content={"message": "Indexing request received", "document_id": data.get("payload", {}).get("documentId")}, status_code=202)
    except Exception as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        return JSONResponse(content={"message": "Indexing failed", "error": str(e)}, status_code=500)


@app.get('/')
async def home():
    logger.info('Home endpoint accessed')
    return JSONResponse(content={"message": "Indexing Service is running"}, status_code=200)



@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def process_extracted_event(message):
    try:
        logger.info(f"📨 Received raw message: {json.dumps(message, indent=2)}")
        
        # Check if this is a valid document.extracted event
        data = message.get("data", {})
        event_type = data.get("eventType")

        if event_type != "DocumentExtracted":
            logger.warning(f"⚠️  Ignoring non-document.extracted event: {event_type}")
            return

        # Extract fields from the DocumentExtracted event
        payload = data.get("payload", {})
        document_id = payload.get("documentId")
        text_content = payload.get("textContent", "")
        extracted_at = payload.get("extractedAt")
        
        # Log the payload structure for debugging
        logger.info(f"🔍 Payload structure: {list(payload.keys())}")
        logger.info(f"📄 Document ID: {document_id}, Text length: {len(text_content)}")

        if not document_id:
            logger.error(f"❌ No documentId found in payload")
            return

        if not text_content:
            logger.error(f"❌ Document {document_id} has no text content to process. Full payload: {json.dumps(payload, indent=2)}")
            return

        # Get metadata
        metadata = payload.get("metadata", {})
        file_type = metadata.get("fileType", payload.get("fileType", "unknown"))
        correlation_id = data.get("correlationId")

        logger.info(f"✅ Processing document {document_id} with {len(text_content)} characters", extra={"correlation_id": correlation_id})

        # Generate chunks and embeddings
        chunk_metadata = {
            "document_id": document_id,
            "file_type": file_type,
            "correlation_id": correlation_id,
            **metadata
        }
        
        chunks = chunk_document(text_content, chunk_metadata)
        logger.info(f"📊 Generated {len(chunks)} chunks from document {document_id}", extra={"correlation_id": correlation_id})
        
        # ADD DEBUG: Check what chunks look like before embedding
        if chunks:
            first_chunk = chunks[0]
            logger.info(f"🔍 First chunk structure: keys={list(first_chunk.keys())}, text_length={len(first_chunk.get('text', ''))}", 
                       extra={"correlation_id": correlation_id})
        
        embedded_chunks = embed_chunks(chunks, correlation_id=correlation_id)
        
        # ADD DEBUG: Check what embedded chunks look like
        logger.info(f"📊 Generated {len(embedded_chunks)} embedded chunks", extra={"correlation_id": correlation_id})
        if embedded_chunks:
            first_embedded = embedded_chunks[0]
            logger.info(f"🔍 First embedded chunk: has_text={bool(first_embedded.get('text'))}, has_embedding={bool(first_embedded.get('embedding'))}, has_metadata={bool(first_embedded.get('metadata'))}", 
                       extra={"correlation_id": correlation_id})
            if first_embedded.get('embedding'):
                logger.info(f"🔍 Embedding length: {len(first_embedded['embedding'])}", extra={"correlation_id": correlation_id})
        
        # Store in ChromaDB
        stored_count = store_chunks_in_chromadb(embedded_chunks, collection_name="chunks", correlation_id=correlation_id)
        logger.info(f"✅ Stored {stored_count} chunks in ChromaDB (out of {len(embedded_chunks)} generated)", 
                   extra={"correlation_id": correlation_id})

        # Publish ChunksIndexed events (one per chunk)
        embedding_model = "all-MiniLM-L6-v2"
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host="rabbitmq"))
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic', durable=True)
            total_chunks = len(embedded_chunks)
            
            published_count = 0
            for chunk in embedded_chunks:
                chunk_meta = chunk.get("metadata", {})
                chunk_index = chunk_meta.get("chunk_index", 0)
                chunk_id = f"{document_id}_chunk_{chunk_index}"
                indexed_event = {
                    "eventType": "ChunksIndexed",
                    "eventId": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat(),
                    "correlationId": correlation_id,
                    "source": "indexing-service",
                    "version": EVENT_VERSION,
                    "payload": {
                        "documentId": document_id,
                        "chunkId": chunk_id,
                        "chunkIndex": chunk_index,
                        "chunkText": chunk["text"][:2000] + "..." if len(chunk["text"]) > 2000 else chunk["text"],
                        "totalChunks": total_chunks,
                        "embeddingModel": embedding_model,
                        "metadata": {
                            "title": chunk_meta.get("title", "Unknown Title"),
                            "pageCount": chunk_meta.get("pageCount", 0),
                            "sourceUrl": chunk_meta.get("sourceUrl", "Unknown Source")
                        },
                        "indexedAt": datetime.utcnow().isoformat()
                    }
                }
                channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key="ChunksIndexed",
                    body=json.dumps(indexed_event),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/json',
                        correlation_id=correlation_id
                    )
                )
                published_count += 1
            
            connection.close()
            logger.info(f"📤 Published {published_count} ChunksIndexed events for document {document_id}", 
                       extra={"correlation_id": correlation_id})
            
        except Exception as e:
            logger.error(f"❌ Failed to publish ChunksIndexed events: {e}", extra={"correlation_id": correlation_id}, exc_info=True)

    except Exception as e:
        logger.error(f"💥 Error indexing document: {e}", exc_info=True)
        raise

    

@app.get('/debug/queue')
async def debug_queue():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host="rabbitmq"))
        channel = connection.channel()
        queue_state = channel.queue_declare(queue=QUEUE_NAME, durable=True, passive=True)
        message_count = queue_state.method.message_count
        connection.close()
        return JSONResponse(content={
            "queue_name": QUEUE_NAME,
            "message_count": message_count,
            "exchange": EXCHANGE_NAME,
            "routing_key": ROUTING_KEY
        }, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get('/debug/chunks')
async def debug_chunks():
    try:
        client = chromadb.PersistentClient(path=chromadb_path)
        collection = client.get_or_create_collection(name="chunks")
        results = collection.get()
        preview = []
        for i, doc in enumerate(results.get('documents', [])):
            preview.append({
                'id': results['ids'][i],
                'text': doc[:200] + ("..." if len(doc) > 200 else ""),
                'metadata': results['metadatas'][i]
            })
        return JSONResponse(content={
            'chunk_count': len(preview),
            'chunks': preview
        }, status_code=200)
    except Exception as e:
        return JSONResponse(content={'error': str(e)}, status_code=500)


def start_consumer():
    indexing_consumer = EventConsumer(EventTypes.DOCUMENT_EXTRACTED.value, process_extracted_event)
    indexing_consumer.daemon = True
    indexing_consumer.start()

@app.on_event("startup")
def on_startup():
    start_consumer()