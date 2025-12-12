"""FastAPI application for extraction service."""

import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone

from extractor import ExtractionService
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("extraction")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

app = FastAPI(title="MARP Ingestion Service", version="1.0.0")

rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
service = ExtractionService(rabbitmq_host)


@app.get("/")
async def home():
    """Root endpoint."""
    logger.info("Home endpoint accessed")
    return JSONResponse(
        content={"message": "Extraction Service is running"}, status_code=200
    )


@app.get("/health")
async def health():
    """Health check."""
    rabbitmq_status = (
        "healthy"
        if service.consumer.connection and not service.consumer.connection.is_closed
        else "unhealthy"
    )
    status = {
        "status": "healthy" if rabbitmq_status == "healthy" else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "extraction",
        "dependencies": {"rabbitmq": rabbitmq_status},
    }
    return JSONResponse(
        content=status, status_code=200 if rabbitmq_status == "healthy" else 503
    )


@app.post("/extract")
async def extract_document_api(request: Request):
    """Extract text and metadata from a document."""
    data = await request.json()
    file_path = data.get("filePath")
    source_url = data.get("sourceUrl")
    if not file_path:
        raise HTTPException(status_code=400, detail="filePath is required")
    try:
        start_time = time.time()
        result = service.extractor.extract_document(file_path, source_url)
        extracted_file_time = datetime.now(timezone.utc).isoformat()
        processing_time = (time.time() - start_time) * 1000
        metadata = result.get("metadata", {})
        fileType = service.extractor.check_file_type(file_path).split("/")[-1]
        metadata_dict = {"sourceUrl": source_url or "Unknown Source"}
        if "title" in metadata:
            metadata_dict["title"] = metadata["title"]
        if "pageCount" in metadata:
            metadata_dict["pageCount"] = metadata["pageCount"]
        response = {
            "documentId": data.get("documentId"),
            "textContent": "\n\n".join(result.get("page_texts", [])),
            "fileType": fileType,
            "metadata": metadata_dict,
            "extractedAt": extracted_file_time,
            "processingTimeMs": processing_time,
        }
        return response
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def start_consumer():
    """Start RabbitMQ consumer thread."""
    consumer_thread = threading.Thread(target=service.start, daemon=True)
    consumer_thread.start()
    logger.info("Consumer thread started")


@app.on_event("startup")
def on_startup():
    start_consumer()
