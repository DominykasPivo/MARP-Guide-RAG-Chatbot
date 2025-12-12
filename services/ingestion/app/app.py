"""FastAPI application for the MARP ingestion service."""

import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

import aiofiles  # type: ignore[import-untyped]
from discoverer import MARPDocumentDiscoverer
from events import publish_document_discovered_event
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from rabbitmq import EventPublisher
from storage import DocumentStorage

logger = logging.getLogger("ingestion")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

DATA_DIR = os.environ.get("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)
storage = DocumentStorage(DATA_DIR)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
event_publisher = EventPublisher(host=RABBITMQ_HOST)

storage_dir = DATA_DIR
document_discoverer = MARPDocumentDiscoverer(storage_dir)

app = FastAPI(title="MARP Ingestion Service", version="1.0.0")


@app.get("/documents")
async def list_documents():
    """List all documents and their metadata."""
    try:
        documents = storage.list_documents()
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Listing documents failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@app.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Stream a document PDF to the client."""
    file_path = storage.get_pdf_path(document_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document not found")

    async def file_iterator():
        async with aiofiles.open(file_path, "rb") as f:
            chunk = await f.read(1024 * 1024)
            while chunk:
                yield chunk
                chunk = await f.read(1024 * 1024)

    return StreamingResponse(
        file_iterator(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={document_id}.pdf"},
    )


@app.post("/discovery/start")
async def start_discovery(background_tasks: BackgroundTasks):
    """Trigger document discovery in the background."""
    correlation_id = str(uuid.uuid4())

    def discovery_job():
        try:
            new_documents = document_discoverer.discover_and_process_documents(
                correlation_id
            )
            events_published = 0
            for doc in new_documents:
                if publish_document_discovered_event(event_publisher, doc):
                    events_published += 1
            logger.info(
                "Background discovery completed.",
                extra={
                    "correlation_id": correlation_id,
                    "documents": len(new_documents),
                    "events_published": events_published,
                },
            )
        except Exception as e:
            logger.error(
                "Background discovery error: %s",
                str(e),
                extra={"correlation_id": correlation_id},
            )

    background_tasks.add_task(discovery_job)
    return {
        "message": "Document discovery started in background",
        "job_status": "running",
    }


@app.get("/")
async def home():
    """Root endpoint to verify service status."""
    logger.info("Home endpoint accessed.")
    return {"message": "Ingestion Service is running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    rabbitmq_status = (
        "healthy"
        if event_publisher and event_publisher._ensure_connection()
        else "unhealthy"
    )
    status = {
        "status": "healthy" if rabbitmq_status == "healthy" else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "ingestion",
        "dependencies": {"rabbitmq": rabbitmq_status},
    }
    return JSONResponse(
        content=status, status_code=200 if rabbitmq_status == "healthy" else 503
    )


def run_discovery_background() -> None:
    """Run periodic document discovery on a background thread."""

    def discovery():
        logger.info("Starting periodic document discovery.")
        while True:
            try:
                logger.info("Running document discovery cycle.")
                correlation_id = str(uuid.uuid4())
                new_documents = document_discoverer.discover_and_process_documents(
                    correlation_id
                )
                for doc in new_documents:
                    publish_document_discovered_event(event_publisher, doc)
                logger.info(
                    "Discovery cycle complete.",
                    extra={
                        "correlation_id": correlation_id,
                        "documents": len(new_documents),
                    },
                )
            except Exception as e:
                logger.error(
                    "Periodic discovery error: %s",
                    str(e),
                    extra={"correlation_id": correlation_id},
                )
            logger.info("Sleeping for 10 minutes before next discovery cycle.")
            time.sleep(600)

    threading.Thread(target=discovery, daemon=True).start()


@app.on_event("startup")
def start_background_discovery() -> None:
    """Start the periodic discovery loop on application startup."""
    run_discovery_background()
