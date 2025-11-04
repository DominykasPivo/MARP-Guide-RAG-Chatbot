import os
from rabbitmq import EventPublisher
from flask import Flask, request, jsonify, g, send_file, Response # g is for request context
from datetime import datetime
import json   
import time
import uuid # for generating correlation IDs
from functools import wraps # for the decorator
from discoverer import MARPDocumentDiscoverer
from events import EventTypes, DocumentDiscovered
from logging_config import setup_logger
from storage import DocumentStorage
import threading
# Set up logging with service name
logger = setup_logger('ingestion')

def with_correlation_id(f):
    """Decorator that ensures correlation ID is set for the request."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Add request start time for timing
        request.start_time = time.time()
        
        # Set correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        g.correlation_id = correlation_id
        
        return f(*args, **kwargs)
    return decorated

app = Flask(__name__)

# Initialize storage 
storage = DocumentStorage("/data")

@app.route('/documents', methods=['GET'])
@with_correlation_id
def list_documents():
    """List all documents with their metadata."""
    documents = storage.list_documents()
    for doc in documents:
        meta = storage.get_metadata(doc['document_id'])
        if meta:
            doc.update(meta)
    accept = request.headers.get('Accept', '')
    is_browser = getattr(request.user_agent, 'browser', None)
    # If browser or JSON requested, use Flask jsonify (compact)
    if accept.startswith('application/json') or is_browser:
        return jsonify({'documents': documents})
    # Otherwise, pretty-print JSON for better readability (e.g., PowerShell, cmd, curl)
    pretty = json.dumps({'documents': documents}, indent=2, ensure_ascii=False)
    return Response(pretty, mimetype='application/json')

@app.route('/documents/<document_id>', methods=['GET'])
@with_correlation_id
def get_document(document_id: str):
    """Get a document's PDF content."""
    pdf_bytes = storage.get_pdf(document_id)
    if not pdf_bytes:
        return jsonify({'error': 'Document not found'}), 404
    # Stream PDF content as file
    from io import BytesIO
    return send_file(BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=f'{document_id}.pdf')


# Initialize RabbitMQ event publisher
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
event_publisher = EventPublisher(host=RABBITMQ_HOST)

# Initialize document discoverer
storage_dir = "/data"
document_discoverer = MARPDocumentDiscoverer(storage_dir)


def publish_document_discovered_event(doc_info: DocumentDiscovered):
    """Publish a DocumentDiscovered event to RabbitMQ using EventPublisher."""
    correlation_id = doc_info.correlation_id
    result = event_publisher.publish_event(EventTypes.DOCUMENT_DISCOVERED, doc_info, correlation_id=correlation_id)
    if result:
        logger.info(f"Published document discovery event for {doc_info.document_id}", extra={'correlation_id': correlation_id})
    else:
        logger.error(f"Failed to publish DocumentDiscovered event for {doc_info.document_id}", extra={'correlation_id': correlation_id})
    return result

@app.route('/discovery/start', methods=['POST'])
@with_correlation_id
def start_discovery():
    """Endpoint to trigger document discovery as a background job."""
    correlation_id = g.correlation_id

    def discovery_job():
        try:
            new_documents = document_discoverer.discover_and_process_documents(correlation_id)
            events_published = 0
            for doc in new_documents:
                if publish_document_discovered_event(doc):
                    events_published += 1
            logger.info(f"Background discovery completed: {len(new_documents)} documents, {events_published} events published", extra={'correlation_id': correlation_id})
        except Exception as e:
            logger.error(f"Error during background document discovery: {str(e)}", extra={'correlation_id': correlation_id})

    threading.Thread(target=discovery_job, daemon=True).start()
    return jsonify({
        "message": "Document discovery started in background",
        "job_status": "running"
    }), 202

@app.route('/', methods=['GET'])
def home():
    logger.info('Home endpoint accessed')
    return jsonify({"message": "Ingestion Service is running"}), 200

@app.route('/health', methods=['GET'])
@with_correlation_id
def health():
    # Check RabbitMQ connection
    rabbitmq_status = "healthy" if event_publisher and event_publisher._ensure_connection() else "unhealthy"
    status = {
        "status": "healthy" if rabbitmq_status == "healthy" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "ingestion",
        "dependencies": {
            "rabbitmq": rabbitmq_status
        }
    }
    return jsonify(status), 200 if rabbitmq_status == "healthy" else 503

@app.after_request
def log_response(response):
    logger.info('Request completed', extra={
        'method': request.method,
        'path': request.path,
        'status_code': response.status_code,
        'response_time_ms': (time.time() - request.start_time) * 1000 if hasattr(request, 'start_time') else None
    })
    return response

@app.errorhandler(Exception)
def handle_error(error):
    logger.error('Error occurred', extra={
        'error_type': error.__class__.__name__,
        'error_message': str(error),
        'method': request.method,
        'url': request.url,
        'path': request.path
    }, exc_info=True)
    return jsonify({
        "error": "Internal server error",
        "message": str(error)
    }), 500

def run_discovery_background():
    import threading
    import time

    def periodic_discovery():
        while True:
            logger.info('Running periodic document discovery...')
            try:
                new_documents = document_discoverer.discover_and_process_documents('auto-discovery')
                for doc in new_documents:
                    publish_document_discovered_event(doc)
                logger.info(f'Periodic discovery complete. Documents found: {len(new_documents)}')
            except Exception as e:
                logger.error(f'Error during periodic discovery: {e}')
            time.sleep(600)  # 10 minutes

    def initial_discovery():
        logger.info('Running initial document discovery on startup (background)...')
        try:
            new_documents = document_discoverer.discover_and_process_documents('startup')
            for doc in new_documents:
                publish_document_discovered_event(doc)
            logger.info(f'Initial discovery complete. Documents found: {len(new_documents)}')
        except Exception as e:
            logger.error(f'Error during initial discovery: {e}')

    # Start both initial and periodic discovery in background threads
    threading.Thread(target=initial_discovery, daemon=True).start()
    threading.Thread(target=periodic_discovery, daemon=True).start()


if __name__ == '__main__':
    run_discovery_background()
    logger.info('Starting Ingestion Service...')
    logger.info('Registered routes:')
    for rule in app.url_map.iter_rules():
        logger.info(f"Route: {rule.rule} -> {rule.endpoint}")
    app.run(host='0.0.0.0', port=8000, use_reloader=False)