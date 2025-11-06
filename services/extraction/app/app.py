import json
import os
import time
from datetime import datetime, timezone
import uuid
import pika
from functools import wraps
from dataclasses import asdict # for converting dataclasses to dicts (metadata > dict > JSON serialization)
from flask import Flask, jsonify, g, request
from rabbitmq import EventConsumer
from events import DocumentDiscovered, EventTypes
from extractor import PDFExtractor
from logging_config import setup_logger
import threading



# Set up logging with service name
logger = setup_logger('extraction')


# Initialize Flask
app = Flask(__name__)

def with_correlation_id(f):
    """Decorator that ensures correlation ID is set for the request."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Add request start time for timing
        request.start_time = time.time()
        
        correlation_id = request.headers.get('X-Correlation-ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        g.correlation_id = correlation_id
        return f(*args, **kwargs)
    return decorated

class ExtractionService:
    """Service for extracting text and metadata from documents."""
    
    def __init__(self, rabbitmq_host: str = 'rabbitmq'):
        """Initialize the service.
        
        Args:
            rabbitmq_host: Hostname of the RabbitMQ server
        """
        self.consumer = EventConsumer(rabbitmq_host)
        self.extractor = PDFExtractor()
        self.ingestion_url = os.getenv('INGESTION_SERVICE_URL', 'http://ingestion:8000')
        
    def _handle_event(self, ch, method, properties, body):
        """Handle incoming RabbitMQ messages.
        
        Args:
            ch: Channel
            method: Method frame
            properties: Message properties
            body: Message body
        """
        # Get or generate correlation ID
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        
        # Call _handle_document_wrapper to ensure proper correlation ID handling
        self._handle_document_wrapper(ch, method, properties, body)
            
    def start(self):
        """Start the service."""
        logger.info("Starting extraction service...")
        
        # Subscribe to document.discovered events
        if self.consumer.subscribe(EventTypes.DOCUMENT_DISCOVERED.value, self._handle_event):
            self.consumer.start_consuming()
        else:
            raise RuntimeError("Failed to subscribe to events")
            
    def _handle_document_wrapper(self, ch, method, properties, body):
        """Wrapper to ensure correlation ID is preserved before calling handle_document."""
        # Get or generate correlation ID
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        
        if not properties or not properties.correlation_id:
            logger.warning("No correlation ID in message properties, generating new one", extra={
                'correlation_id': correlation_id,
                'routing_key': method.routing_key if method else None
            })
            
            # Create new properties with correlation ID
            properties = pika.BasicProperties(
                correlation_id=correlation_id,
                content_type=properties.content_type if properties else None,
                delivery_mode=2  # Make message persistent
            )
        
        # Call handle_document with properties containing correlation ID
        self.handle_document(ch, method, properties, body)
            
    def handle_document(self, ch, method, properties, body):
        """Handle a document.discovered event.
        
        Args:
            ch: Channel
            method: Method frame
            properties: Message properties
            body: Message body
        """
        # Get correlation ID from properties (should be set by wrapper)
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        logger.info(f"Handling document message", extra={'correlation_id': correlation_id})
        try:
            # Parse message body
            message = json.loads(body)
            event_data = message.get('data', {})

            logger.info("Handling document message", extra={'correlation_id': correlation_id})

            # Deserialize to DocumentDiscovered event  -> Full event structure
            discovered = DocumentDiscovered(
                eventType=message['eventType'],
                eventId=message['eventId'],
                timestamp=message['timestamp'],
                correlationId=message['correlationId'],
                source=message['source'],
                version=message['version'],
                payload=message['payload'] # This is where the document data lives
            )
             # Extract the actual document data from the payload

            logger.info("Processing document", extra={
                'correlation_id': discovered.correlationId,
                'document_id': discovered.payload['documentId'],
                'source_url': discovered.payload['sourceUrl'],
                'discovered_at': discovered.payload['discoveredAt']
            })
            
            # Debug log to inspect the payload of DocumentDiscovered
            logger.debug(f"Discovered event: {discovered}")
            
            # Extract text and metadata
            start_time = time.time()
            file_path = discovered.payload["filePath"]
            result = self.extractor.extract_document(file_path, discovered.payload.get("sourceUrl"))
            extracted_file_time = datetime.now(timezone.utc).isoformat()
            processing_time = (time.time() - start_time) * 1000  # ms
            
            # Extract metadata from the result
            metadata = result.get("metadata", {})
            
            # Use page count from event if present, otherwise fallback to PDF extraction
            page_count = metadata.get("pageCount")
            
            # version to reflect backward-compatible changes
            event_version = os.getenv("EVENT_VERSION", "1.0")
            time_now = datetime.now(timezone.utc).isoformat()

            #get the file type
            fileType = self.extractor.check_file_type(file_path)
            fileType = fileType.split('/')[-1]  # Keep only the part after the last '/'  normally it would be application/pdf
            
            # Refactor event_data to match the new schema

            event_data = {
                "eventType": "DocumentExtracted",
                "eventId": str(uuid.uuid4()),
                "timestamp": time_now,
                "correlationId": correlation_id,
                "source": "extraction-service",
                "version": event_version,  # Incremented version to reflect backward-compatible changes
                "payload": {
                    "documentId": discovered.payload.get("documentId"),
                    "textContent": "\n\n".join(result.get("page_texts", [])),  # Ensure page_texts is handled safely
                    "fileType": fileType,
                    "metadata": {
                        "title": metadata.get("title", "Unknown Title"),  # Default to "Unknown Title" if missing
                        "sourceUrl": discovered.payload.get("sourceUrl", "Unknown Source"),  # Default to "Unknown Source" if missing
                        "pageCount": page_count
                    },
                    "extractedAt": extracted_file_time
                }
            }
            
            logger.info(f"DOCUMENT_EXTRACTED event data: {json.dumps(event_data, indent=2)}")
            
            # Publish the event with correlation ID
            if self.consumer.publish("document.extracted", EventTypes.DOCUMENT_EXTRACTED.value, event_data, correlation_id=correlation_id):
                logger.info("Document extraction completed", extra={
                    'correlation_id': correlation_id,
                    'document_id': discovered.payload['documentId'],
                    'title':  metadata.get("title", "Unknown Title"),
                    'page_count': page_count,
                    'processing_time_ms': processing_time
                })
            else:
                logger.error("Failed to publish extracted event", extra={
                    'document_id': discovered.document_id,
                    'error': 'RabbitMQ publish failed'
                })
            
        except Exception as e:
            logger.error(f"Failed to process document", extra={
                'correlation_id': correlation_id if 'correlation_id' in locals() else None,
                'document_id': event_data.get('document_id') if 'event_data' in locals() else None,
                'error': str(e)
            }, exc_info=True)
            # TODO: Handle error (dead letter queue?)


@app.route('/', methods=['GET'])
def home():
    """Home endpoint."""
    logger.info('Home endpoint accessed')
    return jsonify({"message": "Extraction Service is running"}), 200



@app.route('/health', methods=['GET'])
@with_correlation_id
def health():
    """Health check endpoint."""
    # Check RabbitMQ connection
    rabbitmq_status = "healthy" if service.consumer.connection and not service.consumer.connection.is_closed else "unhealthy"

    # Prepare health status
    status = {
        "status": "healthy" if rabbitmq_status == "healthy" else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "extraction",
        "dependencies": {
            "rabbitmq": rabbitmq_status
        }
    }

    # Return status with appropriate HTTP code
    return jsonify(status), 200 if rabbitmq_status == "healthy" else 503


# Example curl command to test the /extract endpoint //   
#curl -X POST http://localhost:8002/extract -H "Content-Type: application/json" -d "{\"filePath\": \"/data/documents/pdfs/aed7db9c7ebfd737f4c508471b776f3b.pdf\", \"sourceUrl\": \"https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/CDDA.pdf\", \"documentId\": \"aed7db9c7ebfd737f4c508471b776f3b\"}"
@app.route('/extract', methods=['POST'])
@with_correlation_id
def extract_document_api():
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
        return jsonify({'error': 'filePath is required'}), 400
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
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error extracting document: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500





# Create service instance
rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
service = ExtractionService(rabbitmq_host)

if __name__ == '__main__':
    # Start the event consumer in a background thread
    consumer_thread = threading.Thread(target=service.start, daemon=True)
    consumer_thread.start()

    # Start the Flask app
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)