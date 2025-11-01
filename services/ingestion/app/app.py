import logging
from logging.handlers import RotatingFileHandler
import os
import pika # RabbitMQ client
from flask import Flask, request, jsonify, g # g is for request context
from datetime import datetime
import json   
import time
import uuid # for generating correlation IDs
from functools import wraps # for the decorator

app = Flask(__name__)

class CorrelationIDFilter(logging.Filter):
    """Filter that injects correlation ID into log records."""
    def filter(self, record):
        try:
            record.correlation_id = getattr(g, 'correlation_id', 'no-correlation-id')
        except:
            record.correlation_id = 'no-correlation-id'
        return True

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

# RabbitMQ Configuration
def setup_rabbitmq():
    max_retries = 5
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            # Get RabbitMQ URL from environment variable or use default
            rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
            
            # Create a connection to RabbitMQ
            connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            channel = connection.channel()
            
            # Declare queues
            channel.queue_declare(queue='document_ingestion', durable=True)
            channel.queue_declare(queue='extraction_queue', durable=True)
            
            return connection, channel
            
        except pika.exceptions.AMQPConnectionError as error:
            if attempt < max_retries - 1:
                logging.warning(f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logging.error("Failed to connect to RabbitMQ after maximum retries")
                raise error

# Configure logging
class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    def __init__(self):
        super().__init__()
        self.default_keys = ['timestamp', 'level', 'correlation_id', 'message', 'logger']

    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record, datefmt='%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'correlation_id': getattr(record, 'correlation_id', 'no-correlation-id'),
            'message': record.getMessage(),
            'logger': record.name
        }

        # Add extra fields from the record
        for key, value in record.__dict__.items():
            if key not in self.default_keys and not key.startswith('_'):
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)

def setup_logger():
    # Create logs directory if it doesn't exist
    log_dir = '/app/logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Set up formatters for the human eye stdout 
    json_formatter = JsonFormatter()
    human_formatter = logging.Formatter(
        '\033[32m%(asctime)s\033[0m [\033[1m%(levelname)s\033[0m] \033[36m%(correlation_id)s\033[0m - %(message)s'
    )

    # File handler for all logs (JSON format for machine processing)
    file_handler = RotatingFileHandler(
        f'{log_dir}/ingestion_service.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.INFO)

    # Console handler (human-readable format with colors)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(human_formatter)
    console_handler.setLevel(logging.INFO)

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Add correlation ID filter
    correlation_filter = CorrelationIDFilter()
    root_logger.addFilter(correlation_filter)
    file_handler.addFilter(correlation_filter)
    console_handler.addFilter(correlation_filter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger

logger = setup_logger()

# Initialize RabbitMQ connection and channel
try:
    rabbitmq_connection, rabbitmq_channel = setup_rabbitmq()
    logger.info("Successfully connected to RabbitMQ")
except Exception as e:
    logger.error(f"Failed to initialize RabbitMQ: {str(e)}")
    rabbitmq_connection = None
    rabbitmq_channel = None

@app.route('/', methods=['GET'])
def home():
    logger.info('Home endpoint accessed')
    return jsonify({"message": "Ingestion Service is running"}), 200

@app.route('/health', methods=['GET'])
@with_correlation_id
def health():
    # Check RabbitMQ connection
    rabbitmq_status = "healthy" if rabbitmq_connection and not rabbitmq_connection.is_closed else "unhealthy"
    
    status = {
        "status": "healthy" if rabbitmq_status == "healthy" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "ingestion",
        "dependencies": {
            "rabbitmq": rabbitmq_status
        }
    }
    
    return jsonify(status), 200 if rabbitmq_status == "healthy" else 503

@app.route('/ingestion/document', methods=['POST'])
@with_correlation_id
def ingest_document():
    if not rabbitmq_connection or rabbitmq_connection.is_closed:
        return jsonify({"error": "RabbitMQ connection is not available"}), 503

    try:
        # Get document data from request
        document_data = request.get_json()
        
        # Validate request
        if not document_data or not isinstance(document_data, dict):
            return jsonify({"error": "Invalid request data"}), 400
        
        # Publish message to RabbitMQ
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key='document_ingestion',
            body=json.dumps(document_data),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
                content_type='application/json',
                headers={'correlation_id': getattr(g, 'correlation_id', str(uuid.uuid4()))}
            )
        )
        
        doc_id = document_data.get('id', 'unknown')
        logger.info("Document ingestion request queued", extra={
            'document_id': doc_id,
            'document_type': document_data.get('type'),
            'source_url': document_data.get('source_url'),
            'queue': 'document_ingestion'
        })
        return jsonify({
            "message": "Document ingestion request accepted",
            "document_id": doc_id,
            "status": "queued"
        }), 202
        
    except Exception as e:
        logger.error(f"Error processing document ingestion request: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500



@app.before_request
def log_request():
    logger.info('Request received', extra={
        'method': request.method,
        'url': request.url,
        'path': request.path,
        'remote_addr': request.remote_addr,
        'headers': dict(request.headers)
    })

@app.after_request
def log_response(response):
    logger.info('Request completed', extra={
        'method': request.method,
        'url': request.url,
        'path': request.path,
        'status_code': response.status_code,
        'status': response.status,
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

if __name__ == '__main__':
    logger.info('Starting Ingestion Service...')
    app.run(host='0.0.0.0', port=8000)
