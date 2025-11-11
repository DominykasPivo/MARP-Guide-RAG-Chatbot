import os
import time
from datetime import datetime, timezone
from functools import wraps
from dataclasses import asdict # for converting dataclasses to dicts (metadata > dict > JSON serialization)
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from extractor import ExtractionService
import logging
import threading
import sys


# Set up logging with service name
logger = logging.getLogger('extraction')

logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more detail
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout
)

app = FastAPI(title="MARP Ingestion Service", version="1.0.0")

rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
service = ExtractionService(rabbitmq_host)


@app.get('/')
async def home():
    """Home endpoint."""
    logger.info('Home endpoint accessed')
    return JSONResponse(content={"message": "Extraction Service is running"}, status_code=200)


@app.get('/health')
async def health():
    """Health check endpoint."""
    rabbitmq_status = "healthy" if service.consumer.connection and not service.consumer.connection.is_closed else "unhealthy"
    status = {
        "status": "healthy" if rabbitmq_status == "healthy" else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "extraction",
        "dependencies": {
            "rabbitmq": rabbitmq_status
        }
    }
    return JSONResponse(content=status, status_code=200 if rabbitmq_status == "healthy" else 503)


# Example curl command to test the /extract endpoint //   
#curl -X POST http://localhost:8002/extract -H "Content-Type: application/json" -d "{\"filePath\": \"/data/documents/pdfs/aed7db9c7ebfd737f4c508471b776f3b.pdf\", \"sourceUrl\": \"https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/CDDA.pdf\", \"documentId\": \"aed7db9c7ebfd737f4c508471b776f3b\"}"
@app.post('/extract')
async def extract_document_api(request: Request):
    """API endpoint to extract text and metadata from a given document file path and sourceUrl.
    
        Expects a JSON payload with the following fields:

        Required:
        - filePath: The path to the document file to be processed.

        Optional:
        - sourceUrl: The URL of the source document (if applicable).
        - documentId: A unique identifier for the document.
    """
    data = request.get_json()
    file_path = data.get('filePath')
    source_url = data.get('sourceUrl')
    if not file_path:
        raise HTTPException(status_code=400, detail='filePath is required')
    try:
        start_time = time.time()
        result = service.extractor.extract_document(file_path, source_url)
        extracted_file_time = datetime.now(timezone.utc).isoformat()
        processing_time = (time.time() - start_time) * 1000  # ms
        metadata = result.get('metadata', {})
        fileType = service.extractor.check_file_type(file_path)
        fileType = fileType.split('/')[-1]
        metadata_dict = {"sourceUrl": source_url or "Unknown Source"}
        if "title" in metadata:
            metadata_dict["title"] = metadata["title"]
        if "pageCount" in metadata:
            metadata_dict["pageCount"] = metadata["pageCount"]
        response = {
            "documentId": data.get('documentId'),
            "textContent": "\n\n".join(result.get("page_texts", [])),
            "fileType": fileType,
            "metadata": metadata_dict,
            "extractedAt": extracted_file_time,
            "processingTimeMs": processing_time
        }
        return response
    except Exception as e:
        logger.error(f"Error extracting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def start_consumer():
    consumer_thread = threading.Thread(target=service.start, daemon=True)
    consumer_thread.start()
    logger.info("Started RabbitMQ consumer thread for extraction service.")

@app.on_event("startup")
def on_startup():
    start_consumer()