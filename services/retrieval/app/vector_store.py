import chromadb
import os
from logging_config import setup_logger

logger = setup_logger('retrieval.vector_store')

class VectorStore:
    def __init__(self):
        # ✅ USE SAME PATH AS INDEXING SERVICE
        chromadb_path = "/data/chromadb"  
        
        logger.info(f"Connecting to ChromaDB at path: {chromadb_path}")
        
        # ✅ Use PersistentClient with SAME path as indexing
        self.client = chromadb.PersistentClient(path=chromadb_path)
        self.collection_name = "chunks"
        self._collection_cache = None
        self._refresh_collection()
    
    def _refresh_collection(self):
        try:
            self._collection_cache = self.client.get_or_create_collection(name=self.collection_name)
            count = self._collection_cache.count()
            logger.info(f"✅ Connected to '{self.collection_name}' with {count} docs")
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}", exc_info=True)
            raise
    
    @property
    def collection(self):
        if self._collection_cache is None:
            self._refresh_collection()
        return self._collection_cache
    
    def invalidate_cache(self):
        self._collection_cache = None
    
    def query_by_text(self, query_text: str, limit: int = 5) -> dict:
        try:
            count = self.collection.count()
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