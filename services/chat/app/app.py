import os
import time
import json
import uuid
import logging
from flask import Flask, jsonify, request
import pika
import httpx
from models import ChatRequest, ChatResponse, Chunk, Citation
from llm_rag_helpers import generate_answer_with_citations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_URL = os.getenv('RABBITMQ_URL', f'amqp://guest:guest@{RABBITMQ_HOST}:5672/')
RETRIEVAL_SERVICE_URL = os.getenv('RETRIEVAL_SERVICE_URL', 'http://retrieval-service:8000')

def publish_query_event(query: str, correlation_id: str):
    """✅ PUBLISH queryreceived EVENT - THIS IS THE KEY CHANGE"""
    try:
        logger.info(f"🔌 Publishing query event to RabbitMQ")
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        
        channel.exchange_declare(
            exchange='document_events',
            exchange_type='topic',
            durable=True
        )
        
        event = {
            'query': query,
            'correlation_id': correlation_id,
            'timestamp': time.time()
        }
        
        channel.basic_publish(
            exchange='document_events',
            routing_key='queryreceived',
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            )
        )
        
        logger.info(f"📤 Published queryreceived event: {correlation_id}")
        connection.close()
        
    except Exception as e:
        logger.error(f"❌ Error publishing query event: {str(e)}", exc_info=True)

def get_chunks_via_http(query: str):
    """Get chunks from retrieval service via HTTP (fallback method)"""
    try:
        logger.info(f"🔍 Querying retrieval service via HTTP: {RETRIEVAL_SERVICE_URL}")
        
        response = httpx.post(
            f"{RETRIEVAL_SERVICE_URL}/query",
            json={"query": query},
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            chunks = data.get('chunks', [])
            logger.info(f"✅ Retrieved {len(chunks)} chunks via HTTP")
            return chunks
        else:
            logger.error(f"❌ HTTP request failed: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error getting chunks via HTTP: {str(e)}", exc_info=True)
        return []

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    logger.info("Health check requested")
    return jsonify({"status": "healthy"}), 200

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.get_json()
        query = data.get('query')
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        correlation_id = str(uuid.uuid4())
        logger.info(f"💬 Received chat request: '{query}' (correlation_id: {correlation_id})")
        
        # ✅ PUBLISH queryreceived EVENT - THIS IS THE KEY ADDITION
        publish_query_event(query, correlation_id)
        
        # Get chunks via HTTP (immediate response approach)
        logger.info("📊 Fetching chunks from retrieval service...")
        chunks_data = get_chunks_via_http(query)
        
        if not chunks_data:
            logger.warning("⚠️ No chunks found for query")
            return jsonify({
                "answer": "I couldn't find any relevant information to answer your question.",
                "citations": []
            }), 200
        
        # Convert to Chunk objects
        chunks = [Chunk(**chunk) for chunk in chunks_data]
        logger.info(f"✅ Processing {len(chunks)} chunks")
        
        # Generate answer with citations using LLM
        logger.info("🤖 Generating answer with LLM...")
        answer, citations = generate_answer_with_citations(query, chunks)
        
        logger.info(f"✅ Generated answer with {len(citations)} citations")
        
        response = ChatResponse(
            answer=answer,
            citations=citations
        )
        
        return jsonify(response.dict()), 200
        
    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting Chat Service on port 8000")
    app.run(host='0.0.0.0', port=8000)