import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

import aiofiles
from discoverer import MARPDocumentDiscoverer
from events import publish_document_discovered_event
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from rabbitmq import EventPublisher
from storage import DocumentStorage

logger = logging.getLogger("ingestion")

logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more detail
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)



# Use a writable data directory, configurable via environment variable
DATA_DIR = os.environ.get("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)
storage = DocumentStorage(DATA_DIR)

# Initialize RabbitMQ event publisher
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
event_publisher = EventPublisher(host=RABBITMQ_HOST)

# Initialize document discoverer
storage_dir = DATA_DIR
document_discoverer = MARPDocumentDiscoverer(storage_dir)


app = FastAPI(title="MARP Ingestion Service", version="1.0.0")


@app.get("/documents")
async def list_documents():
    """List all documents with their metadata."""
    try:
        documents = storage.list_documents()
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@app.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Download the document as PDF using aiofiles."""
    file_path = storage.get_pdf_path(
        document_id
    )  # You may need to implement this method to get the file path
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
    """Trigger document discovery as a background job."""
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
                f"Background discovery completed: "
                f"{len(new_documents)} documents, "
                f"{events_published} events published",
                extra={"correlation_id": correlation_id},
            )
        except Exception as e:
            logger.error(
                f"Error during background document discovery: {str(e)}",
                extra={"correlation_id": correlation_id},
            )

    background_tasks.add_task(discovery_job)
    return {
        "message": "Document discovery started in background",
        "job_status": "running",
    }


@app.get("/")
async def home():
    logger.info("Home endpoint accessed")
    return {"message": "Ingestion Service is running"}


@app.get("/health")
async def health():
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


def run_discovery_background():
    def discovery():
        logger.info("Running auto-discovery on startup and periodically...")
        while True:
            try:
                logger.info("Running document discovery...")
                correlation_id = str(uuid.uuid4())
                new_documents = document_discoverer.discover_and_process_documents(
                    correlation_id
                )
                for doc in new_documents:
                    publish_document_discovered_event(event_publisher, doc)
                logger.info(
                    f"Discovery complete. Documents found: {len(new_documents)}",
                    extra={"correlation_id": correlation_id},
                )
            except Exception as e:
                logger.error(
                    f"Error during auto-discovery: {str(e)}",
                    extra={"correlation_id": correlation_id},
                )
            logger.info("Discovery sleeping for 10 minutes...")
            time.sleep(600)  # 10 minutes

    threading.Thread(target=discovery, daemon=True).start()


@app.on_event("startup")
def start_background_discovery():
    run_discovery_background()
