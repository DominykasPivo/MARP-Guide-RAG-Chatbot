import logging
import os

from qdrant_client import QdrantClient

logger = logging.getLogger("retrieval.vector_store")


class VectorStore:
    def __init__(self):
        # Use the same collection name as the indexing service
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", "chunks")

        logger.info(f"Connecting to Qdrant at {self.qdrant_host}:{self.qdrant_port}")
        self.client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)

    def _refresh_collection(self):
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection_name for c in collections):
                logger.warning(
                    f"Collection '{self.collection_name}' not found in Qdrant. Waiting for indexing."
                )
            else:
                logger.info(f"Connected to Qdrant collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}", exc_info=True)
            raise

    def query_by_text(self, query_text: str, limit: int = 5) -> dict:
        try:
            logger.info(f"Querying Qdrant for: '{query_text[:100]}...' (top {limit})")
            return {}
        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            return {
                "ids": [[]],
                "distances": [[]],
                "metadatas": [[]],
                "documents": [[]],
            }