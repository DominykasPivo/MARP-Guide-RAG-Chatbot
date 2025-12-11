import logging
import os
import sys
import uuid
from typing import Optional

import httpx
from consumers import start_consumer_thread
from events import publish_query_received_event
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from llm_rag_helpers import generate_answers_parallel
from models import ChatResponse, Chunk, Citation, LLMResponse
from pydantic import BaseModel


class ChatRequestModel(BaseModel):
    query: str
    selected_models: Optional[list[str]] = None


# Configure logging
logger = logging.getLogger("chat")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

app = FastAPI(title="MARP Chat Service", version="1.0.0")

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Environment variables
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", f"amqp://guest:guest@{RABBITMQ_HOST}:5672/")
RETRIEVAL_SERVICE_URL = os.getenv("RETRIEVAL_SERVICE_URL", "http://retrieval:8000")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))

# Multiple FREE LLM models to use for parallel generation
LLM_MODELS = os.getenv(
    "LLM_MODELS",
    "google/gemma-2-9b-it:free,meta-llama/llama-3.2-3b-instruct:free,"
    "microsoft/phi-3-mini-128k-instruct:free",
).split(",")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Log configured models (not API key)
_models_preview = [m.strip() for m in LLM_MODELS if m.strip()]
logger.info(f"🧩 Configured LLM models: {_models_preview}")
if not OPENROUTER_API_KEY:
    logger.warning("⚠️ OPENROUTER_API_KEY is not set; LLM calls will fail.")


@app.on_event("startup")
async def startup_event():
    """Start background event consumers on app startup"""
    logger.info("🚀 Starting Chat Service...")
    start_consumer_thread()
    logger.info("✅ Chat Service ready")


def filter_top_citations(
    citations: list[Citation], top_n: int = 3, min_citations: int = 2
) -> list[Citation]:
    if not citations:
        logger.warning("⚠️ filter_top_citations: No citations to filter")
        return []

    for c in citations:
        if hasattr(c, "page") and c.page is not None:
            c.page = max(0, c.page - 1)

    log_msg = (
        f"🔍 Filtering {len(citations)} citations "
        f"(top_n={top_n}, min_citations={min_citations})"
    )
    logger.info(log_msg)
    sorted_citations = sorted(citations, key=lambda c: c.score, reverse=True)
    num_to_return = max(min_citations, min(len(sorted_citations), top_n))
    result = sorted_citations[:num_to_return]
    seen = set()
    deduped = []
    for c in result:
        key = (c.title, c.page)
        if key not in seen:
            deduped.append(c)
            seen.add(key)

    citation_info = [(c.title, c.page, c.score) for c in deduped]
    logger.info(
        f"✅ Returning {len(deduped)} citations after filtering and deduplication: "
        f"{citation_info}"
    )
    return deduped


async def get_chunks_via_http_async(query: str):
    """Get chunks from retrieval service via HTTP."""
    try:
        logger.info(
            f"🔍 Querying retrieval service via HTTP: " f"{RETRIEVAL_SERVICE_URL}"
        )
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RETRIEVAL_SERVICE_URL}/query",
                json={"query": query},
                timeout=float(API_TIMEOUT),
            )
        if response.status_code == 200:
            data = response.json()
            chunks = data.get("chunks", [])
            logger.info(f"✅ Retrieved {len(chunks)} chunks via HTTP (async)")
            return chunks
        else:
            logger.error(f"❌ HTTP request failed: {response.status_code}")
            return []
    except Exception as e:
        logger.error(
            f"❌ Error getting chunks via HTTP (async): {str(e)}", exc_info=True
        )
        return []


@app.get("/")
async def index():
    """Serve the main UI page"""
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {"message": "UI not available. Access /chat endpoint directly."}


@app.get("/health")
async def health():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {"status": "healthy"}


@app.get("/models")
async def get_available_models():
    """Get list of available LLM models"""
    models = [m.strip() for m in LLM_MODELS if m.strip()]
    return {"models": models}


@app.post("/chat")
async def chat(request: Request, chat_request: ChatRequestModel):
    """Main chat endpoint (async)"""
    try:
        query = chat_request.query
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        correlation_id = str(uuid.uuid4())
        logger.info(
            f"💬 Received chat request: '{query}' "
            f"(correlation_id: {correlation_id})"
        )

        # Use selected models or fall back to all configured
        models_to_use = (
            chat_request.selected_models if chat_request.selected_models else LLM_MODELS
        )
        models_to_use = [m.strip() for m in models_to_use if m.strip()]

        if not models_to_use:
            raise HTTPException(status_code=400, detail="No valid models selected")

        logger.info(f"🤖 Using models: {models_to_use}")

        # ✅ PUBLISH QueryReceived EVENT
        # Fire-and-forget tracking (won't affect HTTP logic)
        publish_query_received_event(
            query_text=query, query_id=correlation_id, user_id="anonymous"
        )

        # Get chunks via HTTP (async)
        logger.info("📊 Fetching chunks from retrieval service (async)...")
        chunks_data = await get_chunks_via_http_async(query)

        if not chunks_data:
            logger.warning(
                "⚠️ No chunks found for query; " "returning multi-LLM fallback response"
            )
            fallback_responses = [
                LLMResponse(
                    model=m.strip(),
                    answer=(
                        "I couldn't find any relevant information "
                        "to answer your question."
                    ),
                    citations=[],
                    generation_time=0.0,
                )
                for m in models_to_use
            ]
            response = ChatResponse(query=query, responses=fallback_responses)
            return JSONResponse(status_code=200, content=response.dict())

        # Convert to Chunk objects
        chunks = [Chunk(**chunk) for chunk in chunks_data]
        logger.info(f"✅ Processing {len(chunks)} chunks")

        # Generate answers from multiple LLMs in parallel
        logger.info(
            f"🤖 Generating answers from {len(models_to_use)} " f"models in parallel..."
        )
        llm_responses = await generate_answers_parallel(
            query, chunks, api_key=OPENROUTER_API_KEY, models=models_to_use
        )

        # Filter citations for each response (keep top 3 by score)
        for response in llm_responses:
            response.citations = filter_top_citations(response.citations, top_n=3)

        logger.info(
            f"✅ Generated {len(llm_responses)} responses " f"with filtered citations"
        )

        response = ChatResponse(query=query, responses=llm_responses)

        return JSONResponse(status_code=200, content=response.dict())

    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
