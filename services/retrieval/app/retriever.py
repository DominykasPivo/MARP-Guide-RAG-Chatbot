"""Retriever for Qdrant vector search (matched to indexing service)."""
import os
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer
import torch
import logging

logger = logging.getLogger('retrieval.retriever')

class Retriever:
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        qdrant_host: str = None,
        qdrant_port: int = None,
        collection_name: str = "chunks"
    ):
        # Match indexing service's env var names and defaults
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", embedding_model)
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(qdrant_port or os.getenv("QDRANT_PORT", 6333))
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", collection_name)

        self.encoder = None
        self.client = None

        logger.info("Initializing Retriever with:")
        logger.info(f"  - Embedding model: {self.embedding_model_name}")
        logger.info(f"  - Qdrant host: {self.qdrant_host}:{self.qdrant_port}")
        logger.info(f"  - Collection: {self.collection_name}")

        self._initialize()


    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant chunks using Qdrant."""
        try:
            # Lowercase query for consistent preprocessing
            query_proc = query.lower()
            logger.info(f"Encoding query: '{query_proc[:100]}...'")
            query_embedding = self.encoder.encode(query_proc, convert_to_tensor=False).tolist()

            # Qdrant search
            logger.info(f"🔍 Searching Qdrant collection '{self.collection_name}' for top {top_k} results")
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                with_payload=True,
                with_vectors=False
            )

            chunks: List[Dict[str, Any]] = []
            for result in search_results:
                payload = result.payload or {}
                chunks.append({
                    "id": result.id,
                    "text": payload.get("text", ""),
                    "relevanceScore": result.score,
                    "title": payload.get("title", "MARP Document"),
                    "page": payload.get("page", 0),
                    "url": payload.get("url", ""),
                    "chunkIndex": payload.get("chunk_index", 0),
                })
            logger.info(f"✅ Retrieved {len(chunks)} chunks from Qdrant")
            return chunks
        except Exception as e:
            logger.error(f"❌ Search failed: {e}", exc_info=True)
            return []

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

            # Qdrant client setup
            logger.info(f"Connecting to Qdrant at {self.qdrant_host}:{self.qdrant_port}")
            self.client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)

            # Ensure collection exists (do not create if not found; indexing service should create)
            try:
                collections = self.client.get_collections().collections
                if not any(c.name == self.collection_name for c in collections):
                    logger.warning(f"Collection '{self.collection_name}' not found in Qdrant. Waiting for indexing.")
                else:
                    logger.info(f"Using existing Qdrant collection '{self.collection_name}'")
            except Exception as e:
                logger.error(f"Failed to check Qdrant collections: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Failed to initialize Retriever: {e}", exc_info=True)
            raise

# Singleton
_retriever = None

def get_retriever() -> Retriever:
    """Get or create singleton Retriever."""
    global _retriever
    if _retriever is None:
        logger.info("Creating Retriever singleton")
        _retriever = Retriever(
            embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            collection_name=os.getenv("QDRANT_COLLECTION_NAME", "chunks"),
        )
    return _retriever