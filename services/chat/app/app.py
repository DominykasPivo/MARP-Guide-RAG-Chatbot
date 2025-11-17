
import os
import sys
import time
import json
import uuid
import logging
import pika
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from models import ChatRequest, ChatResponse, Chunk, Citation, LLMResponse
from llm_rag_helpers import generate_answer_with_citations_async, generate_answers_parallel
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

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_URL = os.getenv('RABBITMQ_URL', f'amqp://guest:guest@{RABBITMQ_HOST}:5672/')
RETRIEVAL_SERVICE_URL = os.getenv('RETRIEVAL_SERVICE_URL', 'http://retrieval:8000')

# Multiple FREE LLM models to use for parallel generation
LLM_MODELS = os.getenv('LLM_MODELS', 'google/gemma-2-9b-it:free,meta-llama/llama-3.2-3b-instruct:free,microsoft/phi-3-mini-128k-instruct:free').split(',')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')

# Log configured models (not API key)
try:
    _models_preview = [m.strip() for m in LLM_MODELS if m.strip()]
    logger.info(f"🧩 Configured LLM models: {_models_preview}")
    if not OPENROUTER_API_KEY:
        logger.warning("⚠️ OPENROUTER_API_KEY is not set; LLM calls will fail.")
except Exception:
    pass



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


@app.get('/')
async def index():
    """Serve the main UI page"""
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {"message": "UI not available. Access /chat endpoint directly."}


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
            logger.warning("⚠️ No chunks found for query; returning multi-LLM fallback response")
            # Return a response per configured model to keep schema consistent
            fallback_responses = [
                LLMResponse(
                    model=m.strip(),
                    answer="I couldn't find any relevant information to answer your question.",
                    citations=[],
                    generation_time=0.0
                )
                for m in LLM_MODELS if m.strip()
            ]
            response = ChatResponse(
                query=query,
                responses=fallback_responses
            )
            return JSONResponse(status_code=200, content=response.dict())

        # Convert to Chunk objects
        chunks = [Chunk(**chunk) for chunk in chunks_data]
        logger.info(f"✅ Processing {len(chunks)} chunks")


        # Generate answers from multiple LLMs in parallel
        logger.info(f"🤖 Generating answers from {len(LLM_MODELS)} models in parallel...")
        llm_responses = await generate_answers_parallel(query, chunks, api_key=OPENROUTER_API_KEY, models=LLM_MODELS)

        logger.info(f"✅ Generated {len(llm_responses)} responses from different models")

        response = ChatResponse(
            query=query,
            responses=llm_responses
        )

        return JSONResponse(status_code=200, content=response.dict())

    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
