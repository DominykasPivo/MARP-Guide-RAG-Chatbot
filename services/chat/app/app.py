"""Entry point for the chat service - HTTP-first RAG architecture."""
import json
import os
import time
from datetime import datetime, timezone
import uuid
from functools import wraps
from flask import Flask, jsonify, g, request
import httpx
from logging_config import setup_logger
from events import publish_event, EventTypes
from llm_client import LLMClient
from llm_rag_helpers import build_rag_prompt, extract_citations
from models import Chunk, Citation

# Initialize Flask
app = Flask(__name__)

# Set up logging
logger = setup_logger('chat')

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

class ChatService:
    """Service for handling chat queries with RAG via HTTP."""
    
    def __init__(self):
        """Initialize the service."""
        self.llm_client = None
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
        self.retrieval_url = os.getenv("RETRIEVAL_URL", "http://retrieval:8002/search")
        
    def _ensure_llm_client(self):
        """Lazy initialization of LLM client."""
        if self.llm_client is None:
            self.llm_client = LLMClient()
        return self.llm_client

# Create service instance
service = ChatService()

@app.route('/', methods=['GET'])
def home():
    """Home endpoint."""
    logger.info('Home endpoint accessed')
    return jsonify({"message": "Chat Service is running"}), 200

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
        
        # Check LLM client
        llm_client = service._ensure_llm_client()
        llm_status = "healthy" if llm_client.is_configured() else "degraded"
        
        # Check retrieval service connectivity
        try:
            with httpx.Client(timeout=5.0) as client:
                health_response = client.get(f"{service.retrieval_url.replace('/search', '/health')}")
                retrieval_status = "healthy" if health_response.status_code == 200 else "degraded"
        except:
            retrieval_status = "unhealthy"
        
        status = {
            "status": "healthy" if retrieval_status in ["healthy", "degraded"] else "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "chat",
            "dependencies": {
                "retrieval": retrieval_status,
                "llm": llm_status
            }
        }
        
        response_code = 200 if retrieval_status in ["healthy", "degraded"] else 503
        logger.info("Health check completed", extra={
            'correlation_id': g.correlation_id,
            'status_code': response_code,
            'retrieval_status': retrieval_status,
            'llm_status': llm_status
        })
        
        return jsonify(status), response_code
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", extra={
            'correlation_id': g.correlation_id
        }, exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "chat",
            "error": str(e)
        }), 503

@app.route('/chat', methods=['POST'])
@with_correlation_id
def chat():
    """✅ HTTP-first RAG endpoint (SPEC COMPLIANT).
    
    ARCHITECTURE:
    1. Accept POST /chat with JSON body
    2. Call Retrieval Service via HTTP REST (SYNCHRONOUS)
    3. Build RAG prompt with custom template
    4. Call LLM via OpenRouter
    5. Extract citations from metadata
    6. Emit events for observability (NOT for workflow)
    7. Return answer with citations
    """
    try:
        data = request.get_json()
        
        # Input validation
        if not data:
            logger.error("No JSON data provided", extra={
                'correlation_id': g.correlation_id
            })
            return jsonify({"error": "Request must include JSON data"}), 400
        
        user_id = data.get('userId', 'anonymous')
        query = data.get('query')
        
        # Validate query parameter
        if not query or not isinstance(query, str) or not query.strip():
            logger.error("Invalid query parameter", extra={
                'correlation_id': g.correlation_id
            })
            return jsonify({"error": "Query must be a non-empty string"}), 400
        
        query_id = str(uuid.uuid4())
        
        logger.info("Chat request received", extra={
            'correlation_id': g.correlation_id,
            'query_id': query_id,
            'user_id': user_id,
            'query': query[:100]
        })
        
        # ✅ STEP 1: Emit QueryReceived event (for observability)
        query_received_payload = {
            "queryId": query_id,
            "userId": user_id,
            "queryText": query
        }
        publish_event(EventTypes.QUERY_RECEIVED.value, query_received_payload, service.rabbitmq_url)
        
        # ✅ STEP 2: Call Retrieval Service via HTTP REST (SPEC REQUIREMENT)
        try:
            retrieval_start = time.time()
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    service.retrieval_url,
                    json={
                        "query": query,
                        "top_k": 5
                    },
                    headers={
                        "X-Correlation-ID": g.correlation_id,
                        "X-Query-ID": query_id
                    }
                )
                response.raise_for_status()
                retrieval_data = response.json()
            
            retrieval_time = (time.time() - retrieval_start) * 1000
            
            logger.info("Retrieved chunks via HTTP", extra={
                'correlation_id': g.correlation_id,
                'query_id': query_id,
                'results_count': len(retrieval_data.get('results', [])),
                'retrieval_time_ms': retrieval_time
            })
            
        except httpx.HTTPError as e:
            logger.error(f"Retrieval service call failed: {e}", extra={
                'correlation_id': g.correlation_id,
                'query_id': query_id
            }, exc_info=True)
            return jsonify({"error": "Failed to retrieve context from retrieval service"}), 503
        
        # ✅ STEP 3: Convert retrieval results to Chunk objects
        chunks = []
        retrieved_results = retrieval_data.get('results', [])
        
        for result in retrieved_results:
            metadata = result.get('metadata', {})
            chunk = Chunk(
                text=result.get('text', ''),
                title=metadata.get('title', 'MARP Document'),
                page=metadata.get('page', 1),
                url=metadata.get('url', 'https://marp.edu')
            )
            chunks.append(chunk)
        
        if not chunks:
            logger.warning("No chunks retrieved for query", extra={
                'correlation_id': g.correlation_id,
                'query_id': query_id
            })
            
            # Emit AnswerGenerated event even for empty results
            answer_generated_payload = {
                "queryId": query_id,
                "answerText": "No relevant information found.",
                "citations": [],
                "confidence": 0.0,
                "generatedAt": datetime.now(timezone.utc).isoformat()
            }
            publish_event("AnswerGenerated", answer_generated_payload, service.rabbitmq_url)
            
            return jsonify({
                "queryId": query_id,
                "answer": "I couldn't find relevant information to answer your question. Please try rephrasing or ask about MARP regulations.",
                "citations": []
            }), 200
        
        # ✅ STEP 4: Build RAG prompt using custom template
        rag_prompt = build_rag_prompt(query, chunks)
        
        # ✅ STEP 5: Generate answer using LLM
        llm_start = time.time()
        llm_client = service._ensure_llm_client()
        answer = llm_client.generate(rag_prompt)
        llm_time = (time.time() - llm_start) * 1000
        
        # ✅ STEP 6: Extract citations from metadata (not from LLM output)
        citations = extract_citations(chunks)
        
        # ✅ STEP 7: Emit AnswerGenerated event (SPEC REQUIREMENT - for observability)
        # Calculate confidence from retrieval scores
        avg_confidence = sum(r.get('score', 0) for r in retrieved_results) / len(retrieved_results) if retrieved_results else 0.5
        
        answer_generated_payload = {
            "queryId": query_id,
            "answerText": answer,
            "citations": [
                {
                    "documentId": r.get('metadata', {}).get('documentId', 'unknown'),
                    "chunkId": r.get('metadata', {}).get('chunkId', 'unknown'),
                    "sourcePage": r.get('metadata', {}).get('page', 1)
                } for r in retrieved_results[:len(citations)]
            ],
            "confidence": round(avg_confidence, 2),
            "generatedAt": datetime.now(timezone.utc).isoformat()
        }
        publish_event("AnswerGenerated", answer_generated_payload, service.rabbitmq_url)
        
        # ✅ STEP 8: Emit ResponseGenerated event (for observability)
        response_payload = {
            "queryId": query_id,
            "userId": user_id,
            "answer": answer,
            "citations": [
                {
                    "title": c.title,
                    "page": c.page,
                    "url": c.url
                } for c in citations
            ],
            "modelUsed": llm_client.model_name,
            "retrievalModel": retrieval_data.get('retrieval_model', 'unknown')
        }
        publish_event(EventTypes.RESPONSE_GENERATED.value, response_payload, service.rabbitmq_url)
        
        logger.info("Chat response generated", extra={
            'correlation_id': g.correlation_id,
            'query_id': query_id,
            'retrieval_time_ms': retrieval_time,
            'llm_time_ms': llm_time,
            'total_time_ms': retrieval_time + llm_time,
            'chunks_used': len(chunks),
            'citation_count': len(citations)
        })
        
        # ✅ STEP 9: Return answer with citations (SPEC REQUIREMENT)
        return jsonify({
            "queryId": query_id,
            "answer": answer,
            "citations": [
                {
                    "title": c.title,
                    "page": c.page,
                    "url": c.url
                } for c in citations
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Chat request failed: {str(e)}", extra={
            'correlation_id': g.correlation_id,
            'error': str(e)
        }, exc_info=True)
        return jsonify({"error": str(e)}), 500

# For local testing with python app.py (optional, for debugging)
if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)