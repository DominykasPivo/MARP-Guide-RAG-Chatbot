"""Entry point for the extraction service."""
import json
import os
import time
from datetime import datetime
import uuid
import pika
from functools import wraps
from dataclasses import asdict # for converting dataclasses to dicts (metadata > dict > JSON serialization)
from flask import Flask, jsonify, g, request
from rabbitmq import EventConsumer
from events import DocumentDiscovered, DocumentExtracted, EventTypes, Metadata
from extractor import PDFExtractor
from logging_config import setup_logger

# Initialize Flask
app = Flask(__name__)

# Set up logging with service name
logger = setup_logger('extraction')

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

        try:
            # Parse message body
            message = json.loads(body)
            event_data = message.get('data', {})

            logger.info("Handling document message", extra={'correlation_id': correlation_id})

            # Deserialize to DocumentDiscovered event (now includes correlation_id)
            discovered = DocumentDiscovered(
                document_id=event_data['document_id'],
                title=event_data['title'],
                source_url=event_data['source_url'],
                file_path=event_data['file_path'],
                discovered_at=event_data['discovered_at'],
                correlation_id=correlation_id,
                last_modified=event_data.get('last_modified'),
                page_count=event_data.get('page_count')
            )

            logger.info(f"Processing document {discovered.document_id}", extra={
                'correlation_id': correlation_id,
                'document_id': discovered.document_id,
                'title': discovered.title,
                'file_path': discovered.file_path,
                'discovered_at': discovered.discovered_at
            })
            
            # Extract text and metadata
            start_time = time.time()
            file_path = discovered.file_path.replace('/data/', '/data/', 1)  # No change needed since both use /data
            result = self.extractor.extract_document(file_path)
            processing_time = (time.time() - start_time) * 1000  # ms
            
            # Create metadata
            metadata = Metadata(
                author=result["metadata"].get("author", "Unknown"),
                source_url=discovered.source_url,
                file_type="pdf",
                creation_date=result["metadata"].get("creation_date"),
                last_modified=discovered.last_modified
            )
            
            # Use page count from event if present, otherwise fallback to PDF extraction
            page_count = discovered.page_count if discovered.page_count is not None else result["metadata"].get("page_count")
            
            # Create extracted event
            event_data = {
                "document_id": discovered.document_id,
                "title": discovered.title,
                "text_content": result["text_content"],
                "page_count": page_count,
                "metadata": asdict(metadata) if metadata else {},
                "extracted_at": datetime.utcnow().isoformat()
            }
            
            # Publish the event with correlation ID
            if self.consumer.publish("document.extracted", EventTypes.DOCUMENT_EXTRACTED.value, event_data, correlation_id=correlation_id):
                logger.info("Document extraction completed", extra={
                    'correlation_id': correlation_id,
                    'document_id': discovered.document_id,
                    'title': discovered.title,
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
    try:
        # Log health check request
        logger.info("Health check requested", extra={
            'method': request.method,
            'path': request.path,
            'remote_addr': request.remote_addr,
            'headers': dict(request.headers)
        })
        
        # Check RabbitMQ connection
        rabbitmq_status = "healthy" if service.consumer.connection and not service.consumer.connection.is_closed else "unhealthy"
        
        status = {
            "status": "healthy" if rabbitmq_status == "healthy" else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "extraction",
            "dependencies": {
                "rabbitmq": rabbitmq_status
            },
            "uptime": time.time() - service.consumer.start_time if hasattr(service.consumer, 'start_time') else None,
            "response_time_ms": (time.time() - request.start_time) * 1000 if hasattr(request, 'start_time') else None
        }
        
        response_code = 200 if rabbitmq_status == "healthy" else 503
        logger.info("Health check completed", extra={
            'status_code': response_code,
            'rabbitmq_status': rabbitmq_status,
            'response_time_ms': (time.time() - request.start_time) * 1000 if hasattr(request, 'start_time') else None
        })
        
        return jsonify(status), response_code
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "extraction",
            "error": str(e),
            "response_time_ms": (time.time() - request.start_time) * 1000 if hasattr(request, 'start_time') else None
        }), 503

# Create service instance
rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
service = ExtractionService(rabbitmq_host)

# Start consuming events
service.start()

if __name__ == '__main__':
    # Start the Flask app
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port)