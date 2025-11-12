import os
import logging
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance

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


def store_chunks_in_qdrant(chunks, collection_name=QDRANT_COLLECTION, correlation_id=None):
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
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )

    points = []
    for idx, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        doc_id = meta.get("document_id")
        chunk_index = meta.get("chunk_index", idx)
        if doc_id is not None:
            chunk_id = f"{doc_id}_chunk_{chunk_index}"
        else:
            chunk_id = str(idx)
        point = PointStruct(
            id=chunk_id,
            vector=chunk["embedding"],
            payload={
                **meta,
                "text": chunk["text"]
            }
        )
        points.append(point)

    if points:
        client.upsert(collection_name=collection_name, points=points)
        logger.info(f"Stored {len(points)} new chunks in Qdrant.", extra={"correlation_id": correlation_id})
    else:
        logger.info(f"No new chunks to add.", extra={"correlation_id": correlation_id})
