from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger("indexing")

# Load the model once at module level
model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_chunks(chunks, correlation_id=None):
    """
    Given a list of chunk dicts (with 'text' and 'metadata'), add an 'embedding' field to each using SentenceTransformer.
    Preserves all metadata fields, including chunk-level metadata.
    Returns the same list with embeddings added as lists.
    """
    if not chunks:
        logger.error("No chunks provided for embedding.", extra={"correlation_id": correlation_id})
        raise ValueError("Chunks list is empty.")

    valid_chunks = [chunk for chunk in chunks if chunk.get("text")]
    if not valid_chunks:
        logger.error("All chunks are invalid or have empty 'text' fields.", extra={"correlation_id": correlation_id})
        raise ValueError("No valid chunks with non-empty 'text' fields.")

    texts = [chunk["text"] for chunk in valid_chunks]
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)

    embedded_chunks = []
    for chunk, emb in zip(valid_chunks, embeddings):
        # Create a new dict to avoid mutating input, and preserve all metadata
        embedded_chunk = {
            "text": chunk["text"],
            "metadata": chunk.get("metadata", {}).copy(),
            "embedding": emb.tolist()
        }
        embedded_chunks.append(embedded_chunk)

    logger.info(f"Successfully embedded {len(embedded_chunks)} chunks.", extra={"correlation_id": correlation_id})
    return embedded_chunks

