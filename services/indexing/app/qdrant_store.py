import logging
import os

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

logger = logging.getLogger("indexing.qdrant_store")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "chunks")
VECTOR_SIZE = int(os.getenv("QDRANT_VECTOR_SIZE", 384))  # Adjust to your embedding size


def get_qdrant_client():
    """
    Initialize and return a Qdrant client.
    """
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def store_chunks_in_qdrant(
    chunks, collection_name=QDRANT_COLLECTION, correlation_id=None
):
    """
    Store chunk embeddings, text, and metadata in a Qdrant collection.
    Args:
        chunks: List of dicts with 'embedding', 'text', and optional 'metadata'.
        collection_name: Name of the Qdrant collection.
    """
    client = get_qdrant_client()

    # Ensure collection exists
    if collection_name not in [c.name for c in client.get_collections().collections]:
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    points = []
    import uuid

    for idx, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        # Always generate a new UUID for each chunk's point ID
        chunk_id = str(uuid.uuid4())
        point = PointStruct(
            id=chunk_id,
            vector=chunk["embedding"],
            payload={**meta, "text": chunk["text"]},
        )
        points.append(point)

    if points:
        # Debug: print the first point's structure and vector length
        first_point = points[0]
        logger.info(
            f"First Qdrant point: id={first_point.id}, "
            f"vector_len={len(first_point.vector)}, "
            f"payload_keys={list(first_point.payload.keys())}"
        )
        logger.info(f"First vector sample: {first_point.vector[:10]}")
        logger.info(f"First payload: {first_point.payload}")
        try:
            client.upsert(collection_name=collection_name, points=points)
            logger.info(
                f"Stored {len(points)} new chunks in Qdrant.",
                extra={"correlation_id": correlation_id},
            )
        except Exception as e:
            logger.error(f"❌ Qdrant upsert failed: {e}", exc_info=True)
    else:
        logger.info("No new chunks to add.", extra={"correlation_id": correlation_id})
