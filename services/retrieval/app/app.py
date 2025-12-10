import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

from consumers import start_consumer_thread
from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from qdrant_client import QdrantClient
from retrieval import RetrievalService
from retrieval_events import publish_retrieval_completed_event

# Environment variables
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))


class SearchRequest(BaseModel):
    query: str
    top_k: int = RETRIEVAL_TOP_K


class SearchResult(BaseModel):
    text: str
    title: str
    page: int
    url: str
    score: float


logger = logging.getLogger("retrieval")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)


rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
app = FastAPI(title="MARP Retrieval Service", version="1.0.0")


service = RetrievalService()


@app.on_event("startup")
async def startup_event():
    """Start background event consumers on app startup"""
    logger.info("🚀 Starting Retrieval Service...")
    # Start consuming QueryReceived events (for tracking only - won't affect HTTP logic)
    start_consumer_thread()
    logger.info("✅ Retrieval Service ready")


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

        # Track timing for event
        start_time = time.time()
        correlation_id = str(uuid.uuid4())

        retriever = service._ensure_retriever()
        chunks = retriever.search(query, top_k)

        # Calculate metrics
        processing_time = (time.time() - start_time) * 1000
        top_score = chunks[0]["relevanceScore"] if chunks else 0.0

        # ✅ PUBLISH RetrievalCompleted EVENT
        publish_retrieval_completed_event(
            query_id=correlation_id,
            query=query,
            results_count=len(chunks),
            top_score=float(top_score),
            latency_ms=processing_time,
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
        correlation_id = str(uuid.uuid4())

        retriever = service._ensure_retriever()
        chunks = retriever.search(query_text, top_k)

        processing_time = (time.time() - start_time) * 1000
        top_score = chunks[0].get("relevanceScore", 0.0) if chunks else 0.0

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

        logger.info(
            "Query completed",
            extra={
                "correlation_id": correlation_id,
                "results_count": len(formatted_chunks),
                "processing_time_ms": processing_time,
            },
        )

        # ✅ Prepare response FIRST
        response_data = {"query": query_text, "chunks": formatted_chunks}

        # ✅ Publish event in background thread (fire-and-forget)
        import threading

        def publish_in_background():
            try:
                publish_retrieval_completed_event(
                    query_id=correlation_id,
                    query=query_text,
                    results_count=len(formatted_chunks),
                    top_score=float(top_score),
                    latency_ms=processing_time,
                )
            except Exception as e:
                logger.warning(f"Event publishing failed (non-critical): {e}")

        threading.Thread(target=publish_in_background, daemon=True).start()

        # ✅ Return response immediately (don't wait for event)
        return JSONResponse(response_data, status_code=200)

    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/debug/qdrant-verification")
def verify_qdrant_collection():
    """Comprehensive endpoint to verify Qdrant collection has all chunks."""
    try:
        retriever = service._ensure_retriever()
        qdrant_client = QdrantClient(host=service.qdrant_host, port=service.qdrant_port)

        # Get collection info
        collection_info = qdrant_client.get_collection(service.collection_name)
        total_points = (
            collection_info.points_count
            if hasattr(collection_info, "points_count")
            else collection_info.get("points_count", 0)
        )

        # Get sample of points to analyze
        sample_points, _ = qdrant_client.scroll(
            collection_name=service.collection_name, limit=100  # Get more samples
        )

        # Analyze the sample
        unique_titles = set()
        unique_pages = set()
        chunk_indices = []
        pages_by_title = {}

        for pt in sample_points:
            payload = pt.payload or {}
            title = payload.get("title", "Unknown")
            page = payload.get("page", 0)
            chunk_index = payload.get("chunk_index", 0)

            unique_titles.add(title)
            unique_pages.add((title, page))
            chunk_indices.append(chunk_index)

            if title not in pages_by_title:
                pages_by_title[title] = set()
            pages_by_title[title].add(page)

        # Count chunks per document/page
        chunks_per_doc = {}
        for pt in sample_points:
            payload = pt.payload or {}
            title = payload.get("title", "Unknown")
            page = payload.get("page", 0)
            key = (title, page)
            chunks_per_doc[key] = chunks_per_doc.get(key, 0) + 1

        # Test a search to see how many results we get
        test_query = "academic regulations"
        test_embedding = retriever.encoder.encode(
            test_query.lower(), convert_to_tensor=False
        ).tolist()
        test_results = qdrant_client.search(
            collection_name=service.collection_name,
            query_vector=test_embedding,
            limit=10,
            with_payload=True,
        )

        return JSONResponse(
            {
                "collection_name": service.collection_name,
                "total_points": total_points,
                "sample_analyzed": len(sample_points),
                "statistics": {
                    "unique_documents": len(unique_titles),
                    "unique_document_pages": len(unique_pages),
                    "documents": list(unique_titles),
                    "chunks_per_document_page": {
                        f"{title} - Page {page}": count
                        for (title, page), count in sorted(chunks_per_doc.items())[:20]
                    },
                    "sample_chunk_indices": sorted(set(chunk_indices))[:20],
                },
                "test_search": {
                    "query": test_query,
                    "results_returned": len(test_results),
                    "sample_results": [
                        {
                            "score": r.score,
                            "title": r.payload.get("title", "Unknown"),
                            "page": r.payload.get("page", 0),
                            "chunk_index": r.payload.get("chunk_index", 0),
                            "has_text": bool(r.payload.get("text")),
                        }
                        for r in test_results[:5]
                    ],
                },
                "health": {
                    "has_data": total_points > 0,
                    "has_diverse_data": len(unique_titles) > 1,
                    "has_multiple_chunks": len(set(chunk_indices)) > 1,
                },
            }
        )
    except Exception as e:
        logger.error(f"Verification endpoint failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
