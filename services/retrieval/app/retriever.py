"""Retriever for Qdrant vector search (matched to indexing service)."""

import logging
import os
from typing import Any, Dict, List, Optional

import torch
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("retrieval.retriever")


class Retriever:
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        qdrant_host: Optional[str] = None,
        qdrant_port: Optional[int] = None,
        collection_name: str = "chunks",
    ):
        # Match indexing service's env var names and defaults
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", embedding_model)
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST", "localhost")
        port_value: str | int | None = qdrant_port or os.getenv("QDRANT_PORT")
        self.qdrant_port = int(port_value) if port_value else 6333
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", collection_name)

        self.encoder = None
        self.client = None
        # Add cache tracking for invalidate_cache() method
        self._cache_valid = True

        logger.info("Initializing Retriever with:")
        logger.info(f"  - Embedding model: {self.embedding_model_name}")
        logger.info(f"  - Qdrant host: {self.qdrant_host}:{self.qdrant_port}")
        logger.info(f"  - Collection: {self.collection_name}")

        self._initialize()

    def invalidate_cache(self):
        """
        Invalidate retriever cache when new chunks are indexed.
        Called by retrieval.py when ChunksIndexed event is received.
        Currently just logs - could add actual caching logic later.
        """
        logger.info("♻️ Cache invalidated - next query will use fresh data")
        self._cache_valid = False
        # If you add caching later, clear it here

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant chunks using Qdrant.
        Always returns exactly top_k chunks (or as many as available).
        Requests more from Qdrant to account for deduplication.
        """
        # Reset cache flag on new search
        if not self._cache_valid:
            logger.info("🔄 Using fresh data after cache invalidation")
            self._cache_valid = True

        try:
            # Lowercase query for consistent preprocessing
            query_proc = query.lower()
            logger.info(f"Encoding query: '{query_proc[:100]}...'")
            if not self.encoder:
                raise RuntimeError("Encoder not initialized")
            query_embedding = self.encoder.encode(
                query_proc, convert_to_tensor=False
            ).tolist()

            # Qdrant search
            if not self.client:
                raise RuntimeError("Qdrant client not initialized")

            # Request more results from Qdrant to account for deduplication
            # Request 3x top_k to ensure we get enough unique chunks
            qdrant_limit = max(top_k * 3, 15)  # At least 15, or 3x top_k

            logger.info(
                f"🔍 Searching Qdrant collection '{self.collection_name}' "
                f"for top {qdrant_limit} results (to get {top_k} unique chunks)"
            )

            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=qdrant_limit,
                with_payload=True,
                with_vectors=False,
            )

            logger.info(f"📊 Qdrant returned {len(search_results)} raw results")

            chunks: List[Dict[str, Any]] = []
            seen = set()

            for result in search_results:
                # Stop if we have enough chunks
                if len(chunks) >= top_k:
                    break

                payload = result.payload or {}
                text = payload.get("text", "")
                url = payload.get("url", "")
                chunk_index = payload.get("chunk_index", 0)

                # Use a more specific dedup key that includes chunk_index
                # This ensures different chunks from same page are kept
                dedup_key = (
                    text.strip()[:100],
                    url.strip(),
                    chunk_index,
                )  # First 100 chars of text + url + index

                if dedup_key in seen:
                    continue

                seen.add(dedup_key)
                chunks.append(
                    {
                        "id": result.id,
                        "text": text,
                        "relevanceScore": result.score,
                        "title": payload.get("title", "MARP Document"),
                        "page": payload.get("page", 0),
                        "url": url,
                        "chunkIndex": chunk_index,
                    }
                )

            log_msg = (
                f"✅ Retrieved {len(chunks)} unique chunks from Qdrant "
                f"(requested {top_k}, got {len(chunks)} from "
                f"{len(search_results)} raw results)"
            )
            logger.info(log_msg)

            # If we still don't have enough, log a warning
            if len(chunks) < top_k:
                warning_msg = (
                    f"⚠️ Only retrieved {len(chunks)} chunks (requested {top_k}). "
                    f"This might indicate limited data in Qdrant or "
                    f"aggressive deduplication."
                )
                logger.warning(warning_msg)

            return chunks
        except Exception as e:
            logger.error(f"❌ Search failed: {e}", exc_info=True)
            return []

    def _initialize(self):
        try:
            # Load model on CPU (same as indexing)
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            try:
                self.encoder = SentenceTransformer(
                    self.embedding_model_name, device="cpu"
                )
            except Exception as e1:
                logger.warning(
                    f"Primary model load failed: {e1}. "
                    f"Retrying with safe settings..."
                )
                os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
                os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
                if hasattr(torch, "set_float32_matmul_precision"):
                    torch.set_float32_matmul_precision("high")
                self.encoder = SentenceTransformer(
                    self.embedding_model_name, device="cpu"
                )
            logger.info("Embedding model loaded on CPU")

            # Qdrant client setup
            logger.info(
                f"Connecting to Qdrant at {self.qdrant_host}:{self.qdrant_port}"
            )
            self.client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)

            # Ensure collection exists (do not create if not found; indexing
            # service should create)
            try:
                collections = self.client.get_collections().collections
                if not any(c.name == self.collection_name for c in collections):
                    logger.warning(
                        f"Collection '{self.collection_name}' not found in Qdrant. "
                        f"Waiting for indexing."
                    )
                else:
                    logger.info(
                        f"Using existing Qdrant collection '{self.collection_name}'"
                    )
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
