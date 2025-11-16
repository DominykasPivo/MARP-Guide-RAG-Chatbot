
import os
import sys
import time
import json
import uuid
import logging
import pika
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from models import ChatRequest, ChatResponse, Chunk, Citation
from llm_rag_helpers import generate_answer_with_citations_async
from events import publish_query_event


class ChatRequestModel(BaseModel):
    query: str


# Configure logging

logger = logging.getLogger('chat')
logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout
)

app = FastAPI(title="MARP Chat Service", version="1.0.0")


# Environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_URL = os.getenv('RABBITMQ_URL', f'amqp://guest:guest@{RABBITMQ_HOST}:5672/')
RETRIEVAL_SERVICE_URL = os.getenv('RETRIEVAL_SERVICE_URL', 'http://retrieval:8000')



# Async version of chunk retrieval
async def get_chunks_via_http_async(query: str):
    """Get chunks from retrieval service via HTTP asynchronously."""
    try:
        logger.info(f"🔍 Querying retrieval service via HTTP: {RETRIEVAL_SERVICE_URL}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RETRIEVAL_SERVICE_URL}/query",
                json={"query": query},
                timeout=30.0
            )
        if response.status_code == 200:
            data = response.json()
            chunks = data.get('chunks', [])
            logger.info(f"✅ Retrieved {len(chunks)} chunks via HTTP (async)")
            return chunks
        else:
            logger.error(f"❌ HTTP request failed: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"❌ Error getting chunks via HTTP (async): {str(e)}", exc_info=True)
        return []


@app.get('/health')
async def health():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {"status": "healthy"}



@app.post('/chat')
async def chat(request: Request, chat_request: ChatRequestModel):
    """Main chat endpoint (async)"""
    try:
        query = chat_request.query
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        correlation_id = str(uuid.uuid4())
        logger.info(f"💬 Received chat request: '{query}' (correlation_id: {correlation_id})")

        # ✅ PUBLISH queryreceived EVENT - THIS IS THE KEY ADDITION
        publish_query_event(query, correlation_id)

        # Get chunks via HTTP (async)
        logger.info("📊 Fetching chunks from retrieval service (async)...")
        chunks_data = await get_chunks_via_http_async(query)

        if not chunks_data:
            logger.warning("⚠️ No chunks found for query")
            return JSONResponse(
                status_code=200,
                content={
                    "answer": "I couldn't find any relevant information to answer your question.",
                    "citations": []
                }
            )

        # Convert to Chunk objects
        chunks = [Chunk(**chunk) for chunk in chunks_data]
        logger.info(f"✅ Processing {len(chunks)} chunks")


        # Generate answer with citations using LLM (async)
        logger.info("🤖 Generating answer with LLM (async)...")
        API_KEY = os.getenv("OPENROUTER_API_KEY", "")
        LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet")
        answer, citations = await generate_answer_with_citations_async(query, chunks, api_key=API_KEY, model=LLM_MODEL)

        logger.info(f"✅ Generated answer with {len(citations)} citations")

        response = ChatResponse(
            answer=answer,
            citations=citations
        )

        return JSONResponse(status_code=200, content=response.dict())

    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
