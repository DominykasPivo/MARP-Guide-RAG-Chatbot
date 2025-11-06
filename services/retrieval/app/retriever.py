from sentence_transformers import SentenceTransformer
from vector_store import VectorStore
import os
from logging_config import setup_logger

logger = setup_logger('retrieval.retriever')

class Retriever:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern to reuse same instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        logger.info(f"Initializing retriever with model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.vector_store = VectorStore()
        self.model_name = model_name
    
    def invalidate_cache(self):
        """Invalidate vector store cache when new chunks are indexed."""
        logger.info("Invalidating retriever cache")
        self.vector_store.invalidate_cache()
    
    def search(self, query: str, top_k: int = 5):
        """Search for relevant chunks.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            list: List of retrieved chunks matching ChunksRetrieved event schema
        """
        try:
            # Generate embedding
            embedding = self.model.encode(query).tolist()
            
            # Search vector store
            results = self.vector_store.search(embedding, limit=top_k)
            
            # Format results to match ChunksRetrieved event schema
            chunks = []
            if results and 'ids' in results and results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    
                    # Extract chunk content and metadata for chat service
                    chunk = {
                        "chunkId": results['ids'][0][i],
                        "documentId": metadata.get('documentId', metadata.get('document_id', 'unknown')),
                        "text": metadata.get('text', metadata.get('content', '')),  # ← ADDED
                        "title": metadata.get('title', metadata.get('document_title', 'MARP Document')),  # ← ADDED
                        "page": metadata.get('page', metadata.get('page_number', 1)),  # ← ADDED
                        "url": metadata.get('url', metadata.get('document_url', 'https://marp.edu')),  # ← ADDED
                        "relevanceScore": float(1.0 - distance)  # Convert distance to similarity score
                    }
                    chunks.append(chunk)
                    
                logger.info(f"Retrieved {len(chunks)} chunks for query: {query[:50]}...")
            else:
                logger.warning(f"No chunks found for query: {query[:50]}...")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return []
    
    def get_model_name(self):
        """Get the name of the embedding model being used."""
        return self.model_name

# Backward compatibility
_retriever = None

def get_retriever():
    """Get singleton retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = Retriever.get_instance()
    return _retriever