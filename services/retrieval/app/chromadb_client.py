"""
Legacy chromadb_client wrapper for backward compatibility.
Routes to new retriever module.
"""
from retriever import get_retriever
import logging

logger = logging.getLogger(__name__)

def get_relevant_chunks(query: str, top_k: int = 5):
    """Get relevant chunks from ChromaDB (legacy interface).
    
    Args:
        query: Query text
        top_k: Number of results to return
        
    Returns:
        List of chunk dictionaries
    """
    try:
        retriever = get_retriever()
        chunks = retriever.retrieve(query, top_k=top_k)
        
        # Format for legacy compatibility
        return [
            {
                'text': chunk['text'],
                'title': chunk['title'],
                'page': chunk['page'],
                'url': chunk['url']
            }
            for chunk in chunks
        ]
        
    except Exception as e:
        logger.error(f"Error in get_relevant_chunks: {e}", exc_info=True)
        return []