"""Entry point for the retrieval service - Event-driven architecture."""
import json
import os
import threading
import time
from datetime import datetime, timezone
import uuid
from functools import wraps
from flask import Flask, jsonify, g, request
from logging_config import setup_logger
from retriever import get_retriever
from rabbitmq import EventConsumer
from events import publish_event, EventTypes

# Initialize Flask
app = Flask(__name__)

# Set up logging
logger = setup_logger('retrieval')

def with_correlation_id(f):
    """Decorator that ensures correlation ID is set for the request."""
    @wraps(f)
    def decorated(*args, **kwargs):
        request.start_time = time.time()
        correlation_id = request.headers.get('X-Correlation-ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        g.correlation_id = correlation_id
        return f(*args, **kwargs)
    return decorated

class RetrievalService:
    """Service for retrieving relevant document chunks."""
    
    def __init__(self, rabbitmq_host: str = 'rabbitmq'):
        """Initialize the service.
        
        Args:
            rabbitmq_host: Hostname of the RabbitMQ server
        """
        self.rabbitmq_host = rabbitmq_host
        self.consumer = None
        self.retriever = None
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", f"amqp://guest:guest@{rabbitmq_host}:5672/")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        
    def _ensure_consumer(self):
        """Lazy initialization of RabbitMQ consumer."""
        if self.consumer is None:
            self.consumer = EventConsumer(rabbitmq_host=self.rabbitmq_host)
        return self.consumer
        
    def _ensure_retriever(self):
        """Lazy initialization of retriever."""
        if self.retriever is None:
            self.retriever = get_retriever()
        return self.retriever
            
    def start(self):
        """Start the service."""
        logger.info("Starting retrieval service...")
        
        # Initialize consumer
        consumer = self._ensure_consumer()
        
        # Register all subscriptions FIRST
        try:
            consumer.subscribe('queryreceived', self.handle_query_received)
            logger.info("Registered QueryReceived subscription")
        except Exception as e:
            logger.error(f"Failed to register QueryReceived subscription: {e}")
        
        try:
            consumer.subscribe('chunksindexed', self.handle_chunks_indexed)
            logger.info("Registered ChunksIndexed subscription")
        except Exception as e:
            logger.error(f"Failed to register ChunksIndexed subscription: {e}")
        
        # NOW start consuming (this blocks)
        logger.info("Starting RabbitMQ consumer...")
        consumer.start_consuming()
    
    def handle_chunks_indexed(self, ch, method, properties, body):
        """Handle a ChunksIndexed event from indexing service.
        
        This event is emitted once per chunk indexed.
        
        Args:
            ch: Channel
            method: Method frame
            properties: Message properties
            body: Message body
        """
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())

        try:
            # Parse the event according to event catalogue schema
            event = json.loads(body)
            
            # Validate event structure
            if event.get('eventType') != 'ChunksIndexed':
                logger.warning(f"Unexpected event type: {event.get('eventType')}", extra={
                    'correlation_id': correlation_id
                })
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            payload = event.get('payload', {})
            
            # Extract data according to ChunksIndexed schema (per-chunk event)
            document_id = payload.get('documentId')
            chunk_id = payload.get('chunkId')
            chunk_index = payload.get('chunkIndex', 0)
            total_chunks = payload.get('totalChunks', 1)
            indexed_at = payload.get('indexedAt', 'unknown')
            
            logger.info("Processing ChunksIndexed event", extra={
                'correlation_id': correlation_id,
                'document_id': document_id,
                'chunk_id': chunk_id,
                'chunk_index': f"{chunk_index + 1}/{total_chunks}",
                'indexed_at': indexed_at
            })
            
            # Invalidate vector store cache when final chunk is indexed
            # This ensures we have all chunks before refreshing
            if chunk_index == total_chunks - 1:  # Zero-indexed, so last chunk
                retriever = self._ensure_retriever()
                retriever.invalidate_cache()
                
                logger.info("Final chunk indexed - vector store cache invalidated", extra={
                    'correlation_id': correlation_id,
                    'document_id': document_id,
                    'total_chunks': total_chunks
                })
            else:
                logger.debug("Intermediate chunk indexed - cache not invalidated yet", extra={
                    'correlation_id': correlation_id,
                    'document_id': document_id,
                    'chunk_index': chunk_index + 1,
                    'total_chunks': total_chunks
                })
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse event JSON: {str(e)}", extra={
                'correlation_id': correlation_id
            }, exc_info=True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Failed to process ChunksIndexed event: {str(e)}", extra={
                'correlation_id': correlation_id if 'correlation_id' in locals() else None
            }, exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
    def handle_query_received(self, ch, method, properties, body):
        """Handle a QueryReceived event from the event catalogue.
        
        Args:
            ch: Channel
            method: Method frame
            properties: Message properties
            body: Message body
        """
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())

        try:
            # Parse the event according to event catalogue schema
            event = json.loads(body)
            
            # Validate event structure
            if event.get('eventType') != 'QueryReceived':
                logger.warning(f"Unexpected event type: {event.get('eventType')}", extra={
                    'correlation_id': correlation_id
                })
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            payload = event.get('payload', {})
            
            # Extract data according to QueryReceived schema
            query_id = payload.get('queryId')
            user_id = payload.get('userId', 'unknown')
            query_text = payload.get('queryText')
            
            if not query_text:
                logger.error("Missing queryText in QueryReceived event", extra={
                    'correlation_id': correlation_id
                })
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            logger.info("Processing QueryReceived event", extra={
                'correlation_id': correlation_id,
                'query_id': query_id,
                'user_id': user_id,
                'query': query_text
            })
            
            # Retrieve relevant chunks
            start_time = time.time()
            retriever = self._ensure_retriever()
            chunks = retriever.search(query_text, top_k=5)
            processing_time = (time.time() - start_time) * 1000  # ms
            
            # ✅ EMIT RetrievalCompleted EVENT (spec requirement)
            top_score = chunks[0]['relevanceScore'] if chunks else 0.0
            retrieval_completed_payload = {
                "queryId": query_id,
                "query": query_text,
                "resultsCount": len(chunks),
                "topScore": float(top_score),
                "latencyMs": int(processing_time)
            }
            publish_event("RetrievalCompleted", retrieval_completed_payload, self.rabbitmq_url)
            
            # Create ChunksRetrieved payload according to event catalogue
            payload = {
                "queryId": query_id,
                "retrievedChunks": chunks,
                "retrievalModel": self.embedding_model
            }
            
            # Publish ChunksRetrieved event
            if publish_event(EventTypes.CHUNKS_RETRIEVED.value, payload, self.rabbitmq_url):
                logger.info("Published ChunksRetrieved event", extra={
                    'correlation_id': correlation_id,
                    'query_id': query_id,
                    'chunks_count': len(chunks),
                    'processing_time_ms': processing_time
                })
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                logger.error("Failed to publish ChunksRetrieved event", extra={
                    'correlation_id': correlation_id,
                    'query_id': query_id
                })
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse event JSON: {str(e)}", extra={
                'correlation_id': correlation_id
            }, exc_info=True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Failed to process QueryReceived event: {str(e)}", extra={
                'correlation_id': correlation_id if 'correlation_id' in locals() else None
            }, exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# Create service instance
rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
service = RetrievalService(rabbitmq_host)

# ✅ START CONSUMER THREAD (runs when Uvicorn imports the module)
consumer_thread = threading.Thread(target=service.start, daemon=True)
consumer_thread.start()
logger.info("RabbitMQ consumer thread started")

@app.route('/', methods=['GET'])
def home():
    """Home endpoint."""
    logger.info('Home endpoint accessed')
    return jsonify({"message": "Retrieval Service is running"}), 200

@app.route('/health', methods=['GET'])
@with_correlation_id
def health():
    """Health check endpoint."""
    try:
        logger.info("Health check requested", extra={
            'correlation_id': g.correlation_id,
            'method': request.method,
            'path': request.path,
            'remote_addr': request.remote_addr
        })
        
        # Check RabbitMQ connection
        consumer = service._ensure_consumer()
        rabbitmq_status = "healthy" if consumer.connection and not consumer.connection.is_closed else "unhealthy"
        
        status = {
            "status": "healthy" if rabbitmq_status == "healthy" else "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "retrieval",
            "dependencies": {
                "rabbitmq": rabbitmq_status
            }
        }
        
        response_code = 200 if rabbitmq_status == "healthy" else 503
        logger.info("Health check completed", extra={
            'correlation_id': g.correlation_id,
            'status_code': response_code,
            'rabbitmq_status': rabbitmq_status
        })
        
        return jsonify(status), response_code
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", extra={
            'correlation_id': g.correlation_id
        }, exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "retrieval",
            "error": str(e)
        }), 503

@app.route('/search', methods=['POST'])
@with_correlation_id
def search():
    """✅ HTTP REST endpoint for search (SPEC REQUIREMENT).
    
    Required by specification:
    - Accept POST /search with JSON body
    - Return results in specified format
    - Emit RetrievalCompleted event
    """
    try:
        data = request.get_json()
        
        # Input validation
        if not data:
            logger.error("No JSON data provided", extra={
                'correlation_id': g.correlation_id
            })
            return jsonify({"error": "Request must include JSON data"}), 400
        
        query = data.get('query')
        
        # Validate query parameter
        if query is None:
            logger.error("Missing query parameter", extra={
                'correlation_id': g.correlation_id
            })
            return jsonify({"error": "Missing required parameter: query"}), 400
        
        if not isinstance(query, str):
            logger.error("Invalid query type", extra={
                'correlation_id': g.correlation_id,
                'query_type': type(query).__name__
            })
            return jsonify({"error": "Query must be a string"}), 400
        
        if not query.strip():
            logger.error("Empty query parameter", extra={
                'correlation_id': g.correlation_id
            })
            return jsonify({"error": "Query parameter cannot be empty"}), 400
        
        # Validate top_k parameter
        top_k = data.get('top_k', 5)
        if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
            logger.warning("Invalid top_k value, using default", extra={
                'correlation_id': g.correlation_id,
                'provided_top_k': top_k
            })
            top_k = 5
        
        logger.info(f"Search request received", extra={
            'correlation_id': g.correlation_id,
            'query': query,
            'top_k': top_k
        })
        
        # Perform search
        start_time = time.time()
        retriever = service._ensure_retriever()
        chunks = retriever.search(query, top_k)
        processing_time = (time.time() - start_time) * 1000  # ms
        
        # ✅ EMIT RetrievalCompleted EVENT (spec requirement)
        top_score = chunks[0]['relevanceScore'] if chunks else 0.0
        retrieval_completed_payload = {
            "queryId": g.correlation_id,
            "query": query,
            "resultsCount": len(chunks),
            "topScore": float(top_score),
            "latencyMs": int(processing_time)
        }
        event_published = publish_event("RetrievalCompleted", retrieval_completed_payload, service.rabbitmq_url)
        
        if not event_published:
            logger.warning("Failed to publish RetrievalCompleted event", extra={
                'correlation_id': g.correlation_id
            })

        logger.info(f"Search completed successfully", extra={
            'correlation_id': g.correlation_id,
            'results_count': len(chunks),
            'processing_time_ms': processing_time
        })

        # ✅ RETURN SPEC-COMPLIANT FORMAT
        # Format: { "query": str, "results": [{"text": str, "metadata": {...}, "score": float}] }
        formatted_results = []
        for chunk in chunks:
            formatted_results.append({
                "text": chunk.get('text', ''),
                "metadata": {
                    "title": chunk.get('title', 'MARP Document'),
                    "page": chunk.get('page', 1),
                    "url": chunk.get('url', 'https://marp.edu')
                },
                "score": chunk.get('relevanceScore', 0.0)
            })

        return jsonify({
            "query": query,
            "results": formatted_results
        }), 200
        
    except Exception as e:
        logger.error(f"Search failed: {str(e)}", extra={
            'correlation_id': g.correlation_id,
            'error': str(e)
        }, exc_info=True)
        return jsonify({"error": str(e)}), 500

# For local testing with python app.py (optional, for debugging)
if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)