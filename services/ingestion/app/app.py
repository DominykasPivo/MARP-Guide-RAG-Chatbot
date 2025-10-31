import logging
from logging.handlers import RotatingFileHandler
import os
import pika # RabbitMQ client
from flask import Flask, request, jsonify
from datetime import datetime
import json   
import time

app = Flask(__name__)

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
            
            # Declare exchange
            channel.exchange_declare(
                exchange='documents',
                exchange_type='topic',
                durable=True
            )
            
            # Declare queues with their routing keys
            queues = {
                'document.ingestion': ['document.received.*'],
                'document.extraction': ['document.stored.*'],
                'document.indexing': ['document.extracted.*']
            }
            
            for queue, routing_keys in queues.items():
                channel.queue_declare(queue=queue, durable=True)
                for routing_key in routing_keys:
                    channel.queue_bind(
                        exchange='documents',
                        queue=queue,
                        routing_key=routing_key
                    )
            
            return connection, channel
            
        except pika.exceptions.AMQPConnectionError as error:
            if attempt < max_retries - 1:
                logging.warning(f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logging.error("Failed to connect to RabbitMQ after maximum retries")
                raise error

# Configure logging
def setup_logger():
    # Create logs directory if it doesn't exist
    log_dir = '/app/logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Set up logging format
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler for all logs
    file_handler = RotatingFileHandler(
        f'{log_dir}/ingestion_service.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
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
def ingest_document():
    if not rabbitmq_connection or rabbitmq_connection.is_closed:
        return jsonify({"error": "RabbitMQ connection is not available"}), 503

    try:
        # Get document data from request
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        document_data = request.get_json()
        if not document_data or not isinstance(document_data, dict):
            return jsonify({"error": "Invalid request data"}), 400
        
        # Generate document ID if not provided
        doc_id = document_data.get('id') or str(time.time_ns())
        document_data['id'] = doc_id
        
        # Add metadata
        document_data['received_at'] = datetime.utcnow().isoformat()
        document_data['source'] = request.headers.get('User-Agent', 'unknown')
        
        # Publish to RabbitMQ with topic routing
        rabbitmq_channel.basic_publish(
            exchange='documents',
            routing_key=f'document.received.{document_data.get("type", "default")}',
            body=json.dumps(document_data),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
                content_type='application/json',
                message_id=doc_id,
                timestamp=int(time.time()),
                type='document.received'
            )
        )
        
        logger.info(f"Document ingestion request queued: {doc_id}")
        return jsonify({
            "message": "Document ingestion request accepted",
            "document_id": doc_id,
            "received_at": document_data['received_at'],
            "status": "queued"
        }), 202
        
    except Exception as e:
        logger.error(f"Error processing document ingestion request: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health():
    logger.info('Health check performed')
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "ingestion"
    }), 200

@app.before_request
def log_request():
    logger.info(f'Request received: {request.method} {request.url}')

@app.after_request
def log_response(response):
    logger.info(f'Request completed: {request.method} {request.url} - Status: {response.status}')
    return response

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f'Error occurred: {str(error)}', exc_info=True)
    return jsonify({
        "error": "Internal server error",
        "message": str(error)
    }), 500

if __name__ == '__main__':
    logger.info('Starting Ingestion Service...')
    app.run(host='0.0.0.0', port=8000)
