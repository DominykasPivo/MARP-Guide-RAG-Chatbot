"""
Legacy vector DB client wrapper for backward compatibility.
Routes to new retriever module (Qdrant-based).
"""

import logging

from retriever import get_retriever

logger = logging.getLogger("retrieval.vector_db_client")


def get_relevant_chunks(query: str, top_k: int = 5):
    """Get relevant chunks from the current vector DB (Qdrant)."""
    try:
        retriever = get_retriever()
        chunks = retriever.search(query, top_k=top_k)
        return [
            {
                "text": chunk["text"],
                "title": chunk["title"],
                "page": chunk["page"],
                "url": chunk["url"],
            }
            for chunk in chunks
        ]
    except Exception as e:
        logger.error(f"Error in get_relevant_chunks: {e}", exc_info=True)
        return []