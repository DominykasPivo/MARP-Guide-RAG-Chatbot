import math
from unittest.mock import Mock

from services.retrieval.app.retriever import Retriever


class DummyEmbedding:
    def tolist(self):
        return [1, 0]


class FakeVectorDatabase:
    """Fake: In-memory vector DB (no Qdrant needed)"""

    def __init__(self):
        self.chunks = []

    def insert_chunks(self, chunks, embeddings, metadata):
        for i, chunk in enumerate(chunks):
            self.chunks.append(
                {
                    "text": chunk,
                    "embedding": embeddings[i],
                    "metadata": metadata[i] if isinstance(metadata, list) else metadata,
                }
            )

    def search(self, query_embedding, top_k=5):
        def cosine_sim(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

        scores = [cosine_sim(query_embedding, c["embedding"]) for c in self.chunks]
        sorted_results = sorted(
            zip(self.chunks, scores), key=lambda x: x[1], reverse=True
        )
        return [chunk for chunk, score in sorted_results[:top_k]]


def test_retrieval_service():
    db = FakeVectorDatabase()
    db.insert_chunks(
        chunks=["Exam policy states ...", "Coursework must be ..."],
        embeddings=[[1, 0], [0, 1]],
        metadata=[{"page": 12}, {"page": 5}],
    )
    # Mock encoder and client for Retriever
    retriever = Retriever()
    retriever.encoder = Mock()
    retriever.encoder.encode.return_value = DummyEmbedding()
    retriever.client = Mock()
    # Simulate Qdrant search result
    retriever.client.search.return_value = [
        Mock(payload={"text": "Exam policy states ...", "page": 12}, score=0.99, id=1),
        Mock(payload={"text": "Coursework must be ...", "page": 5}, score=0.88, id=2),
    ]
    results = retriever.search("exam policy", top_k=2)
    assert len(results) == 2
    assert "Exam policy" in results[0]["text"]
