"""Retriever using Chroma PersistentClient (matched to indexing service)."""
import os
from typing import List, Dict, Any
import chromadb
from sentence_transformers import SentenceTransformer
import torch
from logging_config import setup_logger

logger = setup_logger('retrieval.retriever')

class Retriever:
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        chromadb_path: str = None,
        collection_name: str = "chunks"
    ):
        # Match indexing service's env var names and defaults
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", embedding_model)
        self.chromadb_path = chromadb_path or os.getenv("CHROMADB_PATH", "/app/data/chromadb")
        self.collection_name = os.getenv("CHROMA_COLLECTION_NAME", collection_name)

        self.encoder = None
        self.client = None
        self.collection = None

        logger.info("Initializing Retriever with:")
        logger.info(f"  - Embedding model: {self.embedding_model_name}")
        logger.info(f"  - ChromaDB path: {self.chromadb_path}")
        logger.info(f"  - Collection: {self.collection_name}")

        self._initialize()

    def _initialize(self):
        try:
            # Load model on CPU (same as indexing)
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            try:
                self.encoder = SentenceTransformer(self.embedding_model_name, device='cpu')
            except Exception as e1:
                logger.warning(f"Primary model load failed: {e1}. Retrying with safe settings...")
                os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
                os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
                if hasattr(torch, "set_float32_matmul_precision"):
                    torch.set_float32_matmul_precision("high")
                self.encoder = SentenceTransformer(self.embedding_model_name, device='cpu')
            logger.info("Embedding model loaded on CPU")

            # PersistentClient - IDENTICAL TO INDEXING
            logger.info(f"Opening ChromaDB persistent client at: {self.chromadb_path}")
            self.client = chromadb.PersistentClient(path=self.chromadb_path)

            # Get or create collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                count = self.collection.count()
                logger.info(f"Using existing collection '{self.collection_name}' with {count} documents")
                if count == 0:
                    logger.warning("Collection exists but is empty - waiting for indexing")
            except Exception as e:
                logger.warning(f"Collection '{self.collection_name}' not found: {e}")
                # Create empty collection (indexing will populate it)
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"Created empty collection '{self.collection_name}'")

        except Exception as e:
            logger.error(f"Failed to initialize retriever: {e}", exc_info=True)
            raise

    def invalidate_cache(self):
        """Reload collection after indexing events."""
        try:
            if self.client:
                self.collection = self.client.get_collection(name=self.collection_name)
                count = self.collection.count()
                logger.info(f"✅ Collection reloaded: '{self.collection_name}' with {count} documents")
        except Exception as e:
            logger.error(f"Failed to reload collection: {e}", exc_info=True)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant chunks."""
        try:
            if not self.collection:
                logger.warning("Collection not initialized; attempting to fetch now")
                self.collection = self.client.get_collection(name=self.collection_name)

            count = self.collection.count()
            logger.info(f"🔍 Searching collection '{self.collection_name}' with {count} documents")
            
            if count == 0:
                logger.warning("❌ Collection is empty - no documents to search")
                return []

            # Encode query (same encoder as indexing)
            logger.info(f"Encoding query: '{query[:100]}...'")
            query_embedding = self.encoder.encode(query, convert_to_tensor=False).tolist()

            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(max(1, top_k), count),
                include=['documents', 'metadatas', 'distances']
            )

            chunks: List[Dict[str, Any]] = []
            if results and results.get('ids') and len(results['ids']) > 0:
                ids = results['ids'][0]
                documents = results.get('documents', [[]])[0]
                metadatas = results.get('metadatas', [[]])[0]
                distances = results.get('distances', [[]])[0]

                for doc_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
                    m = metadata or {}
                    similarity = 1 - float(distance)
                    chunks.append({
                        "id": doc_id,
                        "text": text,
                        "relevanceScore": similarity,
                        "title": m.get("title", "MARP Document"),
                        "page": m.get("page", 0),
                        "url": m.get("url", ""),
                        "chunkIndex": m.get("chunk_index", 0),
                    })
                
                logger.info(f"✅ Retrieved {len(chunks)} chunks")
            else:
                logger.warning("❌ No results returned from ChromaDB query")

            return chunks
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}", exc_info=True)
            return []

# Singleton
_retriever = None

def get_retriever() -> Retriever:
    """Get or create singleton Retriever."""
    global _retriever
    if _retriever is None:
        logger.info("Creating Retriever singleton")
        _retriever = Retriever(
            embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            chromadb_path=os.getenv("CHROMADB_PATH", "/app/data/chromadb"),
            collection_name=os.getenv("CHROMA_COLLECTION_NAME", "chunks"),
        )
    return _retriever