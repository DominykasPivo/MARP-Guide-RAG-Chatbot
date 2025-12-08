import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from qdrant_client import QdrantClient
from retrieval import RetrievalService
from retrieval_events import publish_event


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResult(BaseModel):
    text: str
    title: str
    page: int
    url: str
    score: float


logger = logging.getLogger("retrieval")

logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more detail
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)


rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
app = FastAPI(title="MARP Retrieval Service", version="1.0.0")


service = RetrievalService()


@app.get("/debug/vector-store")
def debug_vector_store():
    """Debug endpoint to inspect vector store state."""
    try:
        service._ensure_retriever()
        qdrant_client = QdrantClient(host=service.qdrant_host, port=service.qdrant_port)
        collection_info = qdrant_client.get_collection(service.collection_name)
        count = collection_info.get("points_count", 0)
        sample_results = []
        if count > 0:
            # Fetch a few points for preview (Qdrant)
            points = qdrant_client.scroll(
                collection_name=service.collection_name, limit=5
            )[0]
            for pt in points:
                sample_results.append(
                    {
                        "id": pt.get("id"),
                        "payload": pt.get("payload"),
                        "vector": str(pt.get("vector"))[:60] + "...",
                    }
                )
        return JSONResponse(
            {
                "status": "healthy" if count > 0 else "empty",
                "collection_name": service.collection_name,
                "qdrant_host": service.qdrant_host,
                "embedding_model": service.embedding_model,
                "total_points": count,
                "sample_points": sample_results,
                "has_points": count > 0,
            },
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Debug endpoint failed: {e}", exc_info=True)
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.post("/search", response_model=dict)
def search(request: SearchRequest):
    """Direct search endpoint (bypasses events)."""
    try:
        query = request.query
        top_k = request.top_k
        if not isinstance(query, str) or not query.strip():
            return JSONResponse(
                {"error": "Missing required parameter: query"}, status_code=400
            )
        if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
            top_k = 5
        start_time = time.time()
        retriever = service._ensure_retriever()
        chunks = retriever.search(query, top_k)
        processing_time = (time.time() - start_time) * 1000
        correlation_id = str(uuid.uuid4())
        top_score = chunks[0]["relevanceScore"] if chunks else 0.0
        publish_event(
            "RetrievalCompleted",
            {
                "queryId": correlation_id,
                "query": query,
                "resultsCount": len(chunks),
                "topScore": float(top_score),
                "latencyMs": int(processing_time),
            },
            service.rabbitmq_url,
        )
        formatted_results = [
            SearchResult(
                text=c.get("text", ""),
                title=c.get("title", "MARP Document"),
                page=c.get("page", 1),
                url=c.get("url", ""),
                score=c.get("relevanceScore", 0.0),
            )
            for c in chunks
        ]
        return {"query": query, "results": formatted_results}
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/health")
async def health():
    status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "retrieval",
    }
    return JSONResponse(content=status, status_code=200)


@app.post("/query")
def query(data: dict = Body(...)):
    """Alternative query endpoint."""
    try:
        if not data:
            return JSONResponse(
                {"error": "Request must include JSON data"}, status_code=400
            )
        query_text = data.get("query")
        if not query_text:
            return JSONResponse({"error": "Query is required"}, status_code=400)
        top_k = data.get("top_k", 5)
        start_time = time.time()
        retriever = service._ensure_retriever()
        chunks = retriever.search(query_text, top_k)
        processing_time = (time.time() - start_time) * 1000
        formatted_chunks = [
            {
                "text": c.get("text", ""),
                "title": c.get("title", "Unknown"),
                "page": c.get("page", 0),
                "url": c.get("url", ""),
                "score": c.get("relevanceScore", 0.0),
            }
            for c in chunks
        ]
        correlation_id = str(uuid.uuid4())
        logger.info(
            "Query completed",
            extra={
                "correlation_id": correlation_id,
                "results_count": len(formatted_chunks),
                "processing_time_ms": processing_time,
            },
        )
        return JSONResponse(
            {"query": query_text, "chunks": formatted_chunks}, status_code=200
        )
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
