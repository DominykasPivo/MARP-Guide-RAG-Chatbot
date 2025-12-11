import logging
import os

from sentence_transformers import SentenceTransformer

logger = logging.getLogger("indexing.embed_chunks")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
model = SentenceTransformer(EMBEDDING_MODEL)
logger.info(f"Loaded embedding model: {EMBEDDING_MODEL}")


def embed_chunks(chunks, correlation_id=None):
    """Embed text chunks and return the same structures with embeddings."""
    if not chunks:
        logger.error(
            "No chunks provided for embedding.",
            extra={"correlation_id": correlation_id},
        )
        raise ValueError("Chunks list is empty.")

    valid_chunks = [chunk for chunk in chunks if chunk.get("text")]
    if not valid_chunks:
        logger.error(
            "No valid chunks with non-empty text fields.",
            extra={"correlation_id": correlation_id},
        )
        raise ValueError("No valid chunks with non-empty 'text' fields.")

    texts = [chunk["text"].lower() for chunk in valid_chunks]
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)

    embedded_chunks = []
    for chunk, emb in zip(valid_chunks, embeddings):
        embedded_chunk = {
            "text": chunk["text"],
            "metadata": chunk.get("metadata", {}).copy(),
            "embedding": emb.tolist(),
        }
        embedded_chunks.append(embedded_chunk)

    logger.info(
        "Chunks embedded successfully.",
        extra={"count": len(embedded_chunks), "correlation_id": correlation_id},
    )
    return embedded_chunks
