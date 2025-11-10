import os
import threading
import uuid
import time
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from rabbitmq import EventPublisher
from discoverer import MARPDocumentDiscoverer
from events import publish_document_discovered_event
from storage import DocumentStorage

logger = logging.getLogger('ingestion')
logging.basicConfig(level=logging.INFO)


# Ensure /data directory exists before initializing storage
os.makedirs("/data", exist_ok=True)
storage = DocumentStorage("/data")

# Initialize RabbitMQ event publisher
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
event_publisher = EventPublisher(host=RABBITMQ_HOST)

# Initialize document discoverer
storage_dir = "/data"
document_discoverer = MARPDocumentDiscoverer(storage_dir)


app = FastAPI(title="MARP Ingestion Service", version="1.0.0")

@app.get('/documents')
async def list_documents():
    """List all documents with their metadata."""
    try:
        documents = storage.list_documents()
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list documents")



@app.get('/documents/{document_id}')
async def get_document(document_id: str):
    """Download the document as PDF."""
    pdf_bytes = storage.get_pdf(document_id)
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="Document not found")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={document_id}.pdf"}
    )


@app.post('/discovery/start')
async def start_discovery(background_tasks: BackgroundTasks):
    """Trigger document discovery as a background job."""
    correlation_id = str(uuid.uuid4())

    def discovery_job():
        try:
            new_documents = document_discoverer.discover_and_process_documents(correlation_id)
            events_published = 0
            for doc in new_documents:
                if publish_document_discovered_event(event_publisher, doc):
                    events_published += 1
            logger.info(f"Background discovery completed: {len(new_documents)} documents, {events_published} events published", extra={'correlation_id': correlation_id})
        except Exception as e:
            logger.error(f"Error during background document discovery: {str(e)}", extra={'correlation_id': correlation_id})

    background_tasks.add_task(discovery_job)
    return {"message": "Document discovery started in background", "job_status": "running"}


@app.get('/')
async def home():
    logger.info('Home endpoint accessed')
    return {"message": "Ingestion Service is running"}

@app.get('/health')
async def health():
    rabbitmq_status = "healthy" if event_publisher and event_publisher._ensure_connection() else "unhealthy"
    status = {
        "status": "healthy" if rabbitmq_status == "healthy" else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "ingestion",
        "dependencies": {
            "rabbitmq": rabbitmq_status
        }
    }
    return JSONResponse(content=status, status_code=200 if rabbitmq_status == "healthy" else 503)


def run_discovery_background():
    def discovery():
        logger.info('Running auto-discovery on startup and periodically...')
        while True:
            try:
                logger.info('Running document discovery...')
                correlation_id = str(uuid.uuid4())
                new_documents = document_discoverer.discover_and_process_documents(correlation_id)
                for doc in new_documents:
                    publish_document_discovered_event(event_publisher, doc)
                logger.info(f'Discovery complete. Documents found: {len(new_documents)}', extra={'correlation_id': correlation_id})
            except Exception as e:
                logger.error(f"Error during auto-discovery: {str(e)}", extra={'correlation_id': correlation_id})
            logger.info('Discovery sleeping for 10 minutes...')
            time.sleep(600)  # 10 minutes

    threading.Thread(target=discovery, daemon=True).start()


@app.on_event("startup")
def start_background_discovery():
    run_discovery_background()