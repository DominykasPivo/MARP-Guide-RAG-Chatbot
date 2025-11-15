from qdrant_client import QdrantClient
import os
import logging

logger = logging.getLogger("retrieval.vector_store")

class VectorStore:
    def __init__(self):
        # ✅ USE SAME COLLECTION NAME AS INDEXING SERVICE
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", "chunks")

        logger.info(f"Connecting to Qdrant at {self.qdrant_host}:{self.qdrant_port}")
        self.client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
    
    def _refresh_collection(self):
        try:
            # Qdrant: Just check if collection exists
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection_name for c in collections):
                logger.warning(f"Collection '{self.collection_name}' not found in Qdrant. Waiting for indexing.")
            else:
                logger.info(f"✅ Connected to Qdrant collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant: {e}", exc_info=True)
            raise
    
    # Qdrant does not use a collection object in the same way; methods will query directly
    
    def query_by_text(self, query_text: str, limit: int = 5) -> dict:
        try:
            # Example: Use retriever or Qdrant client directly for search
            logger.info(f"Querying Qdrant for: '{query_text[:100]}...' (top {limit})")
            # You would need to encode the query and call self.client.search as in retriever.py
            # This is a placeholder for actual Qdrant search logic
            return {}
            if count == 0:
                logger.warning("⚠️ Collection is empty")
                return {'ids': [[]], 'distances': [[]], 'metadatas': [[]], 'documents': [[]]}
            
            results = self.collection.query(
                query_texts=[query_text],
                n_results=min(limit, count),
                include=['metadatas', 'distances', 'documents']
            )
            
            logger.info(f"✅ Query returned {len(results['ids'][0])} results")
            return results
            
        except Exception as e:
            logger.error(f"❌ Query failed: {e}", exc_info=True)
            return {'ids': [[]], 'distances': [[]], 'metadatas': [[]], 'documents': [[]]}