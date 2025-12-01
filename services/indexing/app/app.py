import logging
import os
import sys

from events import EventTypes, process_extracted_event
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from qdrant_store import get_qdrant_client
from rabbitmq import EXCHANGE_NAME, QUEUE_NAME, ROUTING_KEY, EventConsumer, pika

EVENT_VERSION = os.getenv("EVENT_VERSION", "1.0")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "chunks")


logger = logging.getLogger("indexing")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

app = FastAPI(title="MARP Indexing Service", version="1.0.0")

client = get_qdrant_client()


@app.get("/index/status/{doc_id}")
async def index_status(doc_id: str):
    try:

        res = client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter={
                "must": [{"key": "document_id", "match": {"value": doc_id}}]
            },
            limit=1,
        )
        points = res[0] if res else []
        if points:
            logger.debug(
                f"Returning status for doc_id {doc_id}: indexed, "
                f"chunk_count={len(points)}"
            )
            return JSONResponse(
                content={"indexed": True, "chunk_count": len(points)}, status_code=200
            )
        else:
            logger.warning(
                f"Status requested for unknown or unindexed doc_id: {doc_id}"
            )
            return JSONResponse(content={"indexed": False}, status_code=404)
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        logger.error(f"Error in /index/status/{doc_id}: {e}\nTraceback:\n{tb}")
        return JSONResponse(content={"error": str(e), "traceback": tb}, status_code=500)


@app.get("/health")
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
        client.get_collections()
        status["qdrant"] = "healthy"
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        status["qdrant"] = f"unhealthy ({str(e)})"
    status["status"] = (
        "healthy"
        if all(v == "healthy" for k, v in status.items() if k != "service")
        else "unhealthy"
    )
    return JSONResponse(
        content=status, status_code=200 if status["status"] == "healthy" else 503
    )


@app.post("/index")
async def index(request: Request):
    """Index a document (requires a DocumentExtracted event payload)
    Args:
    > payload{extractedAt, metadata{title, sourceUrl, fileType, pageCount},
      textContent, documentId}, version, source, correlationId, timestamp,
      eventId, eventType

    Example terminal command to test the /index endpoint:
     >curl -X POST http://localhost:8003/index \
       -H "Content-Type: application/json" \
       -d '{"eventType":"DocumentExtracted","eventId":"test-id",
            "timestamp":"2025-11-06T12:00:00Z","payload":{...}}'

    """
    data = await request.json()
    try:
        process_extracted_event({"data": data})
        return JSONResponse(
            content={
                "message": "Indexing request received",
                "document_id": data.get("payload", {}).get("documentId"),
            },
            status_code=202,
        )
    except Exception as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        return JSONResponse(
            content={"message": "Indexing failed", "error": str(e)}, status_code=500
        )


@app.get("/")
async def home():
    logger.info("Home endpoint accessed")
    return JSONResponse(
        content={"message": "Indexing Service is running"}, status_code=200
    )


@app.get("/debug/queue")
async def debug_queue():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host="rabbitmq"))
        channel = connection.channel()
        queue_state = channel.queue_declare(
            queue=QUEUE_NAME, durable=True, passive=True
        )
        message_count = queue_state.method.message_count
        connection.close()
        return JSONResponse(
            content={
                "queue_name": QUEUE_NAME,
                "message_count": message_count,
                "exchange": EXCHANGE_NAME,
                "routing_key": ROUTING_KEY,
            },
            status_code=200,
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/debug/chunks")
async def debug_chunks():
    try:
        res = client.scroll(collection_name=QDRANT_COLLECTION, limit=10)
        points = res[0] if res else []
        preview = []
        for p in points:
            preview.append(
                {
                    "id": p.id,
                    "text": p.payload.get("text", "")[:200]
                    + ("..." if len(p.payload.get("text", "")) > 200 else ""),
                    "metadata": p.payload,
                }
            )
        return JSONResponse(
            content={"chunk_count": len(preview), "chunks": preview}, status_code=200
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


def start_consumer():
    indexing_consumer = EventConsumer(
        EventTypes.DOCUMENT_EXTRACTED.value, process_extracted_event
    )
    indexing_consumer.daemon = True
    indexing_consumer.start()


@app.on_event("startup")
def on_startup():
    start_consumer()
