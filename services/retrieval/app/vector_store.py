import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict
from logging_config import setup_logger

logger = setup_logger('retrieval.vector_store')

class VectorStore:
    def __init__(self):
        # ChromaDB configuration
        host = os.getenv("CHROMA_HOST", "localhost")
        port = int(os.getenv("CHROMA_PORT", "8000"))
        
        logger.info(f"Connecting to ChromaDB at {host}:{port}")
        
        # Create ChromaDB client
        self.client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        self.collection_name = "marp_chunks"
        self._collection_cache = None  # ✅ ADDED: Cache for collection
        
        # Get or create collection
        self._refresh_collection()
    
    def _refresh_collection(self):  # ✅ ADDED
        """Refresh collection reference."""
        try:
            self._collection_cache = self.client.get_collection(name=self.collection_name)
            logger.info(f"Connected to existing collection: {self.collection_name}")
        except Exception:
            # Collection doesn't exist, create it
            self._collection_cache = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "MARP document chunks for retrieval"}
            )
            logger.info(f"Created new collection: {self.collection_name}")
    
    @property  # ✅ ADDED
    def collection(self):
        """Get collection, refresh if needed."""
        if self._collection_cache is None:
            self._refresh_collection()
        return self._collection_cache
    
    def invalidate_cache(self):  # ✅ ADDED
        """Invalidate collection cache to force refresh on next access."""
        logger.info("Invalidating vector store cache")
        self._collection_cache = None
    
    def search(self, embedding: list, limit: int = 5) -> dict:
        """Search for similar vectors in ChromaDB.
        
        Args:
            embedding: Query embedding vector
            limit: Maximum number of results to return
            
        Returns:
            dict: ChromaDB query results with structure:
                {
                    'ids': [[...]],
                    'distances': [[...]],
                    'metadatas': [[...]]
                }
        """
        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit,
                include=['metadatas', 'distances']
            )
            
            num_results = len(results['ids'][0]) if results['ids'] else 0
            logger.info(f"Vector search returned {num_results} results")
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return {'ids': [[]], 'distances': [[]], 'metadatas': [[]]}
    
    def add_chunks(self, chunks: List[Dict]) -> bool:
        """Add chunks to the vector store.
        
        Args:
            chunks: List of chunk dictionaries with 'id', 'text', and 'metadata'
            
        Returns:
            bool: Success status
        """
        try:
            ids = [chunk['id'] for chunk in chunks]
            documents = [chunk['text'] for chunk in chunks]
            metadatas = [chunk['metadata'] for chunk in chunks]
            
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.info(f"Added {len(chunks)} chunks to vector store")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add chunks: {e}")
            return False