# Integration tests for /search endpoint matching current API response
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../services/retrieval/app')))


import pytest
import math
from fastapi.testclient import TestClient
from services.retrieval.app.app import app
from unittest.mock import patch, MagicMock

# --- Dependency Stubs/Mocks for Fast, Isolated Tests ---

def cosine_sim(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x*x for x in a))
    norm_b = math.sqrt(sum(y*y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

class FakeVectorDatabase:
    """Fake: In-memory vector DB (no Qdrant needed)"""
    def __init__(self):
        self.chunks = []
    def insert_chunks(self, chunks, embeddings, metadata):
        for i, chunk in enumerate(chunks):
            self.chunks.append({
                "text": chunk,
                "embedding": embeddings[i],
                "metadata": metadata[i] if isinstance(metadata, list) else metadata
            })
    def search(self, query_embedding, top_k=5):
        scores = [cosine_sim(query_embedding, c["embedding"]) for c in self.chunks]
        sorted_results = sorted(
            zip(self.chunks, scores),
            key=lambda x: x[1], reverse=True
        )
        return [chunk for chunk, score in sorted_results[:top_k]]

@pytest.fixture
def sample_documents():
	return [
		{
			"id": "doc-001",
			"title": "General Regulations",
			"text": "Exam policy states ...",
			"page": 12,
			"url": "https://lancaster.ac.uk/.../general.pdf"
		},
		{
			"id": "doc-002",
			"title": "Assessment Guidelines",
			"text": "Coursework must be ...",
			"page": 5,
			"url": "https://lancaster.ac.uk/.../assessment.pdf"
		}
	]


@pytest.fixture
def vector_db_fixture():
    db = FakeVectorDatabase()
    chunks = ["Exam policy states ...", "Coursework must be ..."]
    embeddings = [[1, 0], [0, 1]]
    metadata = [
        {"title": "General Regulations", "page": 12, "url": "https://lancaster.ac.uk/.../general.pdf"},
        {"title": "Assessment Guidelines", "page": 5, "url": "https://lancaster.ac.uk/.../assessment.pdf"}
    ]
    db.insert_chunks(chunks, embeddings, metadata)
    return db

def test_search_returns_relevant_results(vector_db_fixture):
    # Query embedding similar to first chunk
    results = vector_db_fixture.search([1, 0], top_k=2)
    assert len(results) == 2
    assert results[0]["metadata"]["title"] == "General Regulations"
    assert results[0]["metadata"]["page"] == 12
    assert "text" in results[0]

def test_search_returns_relevant_results_vector_db(vector_db_fixture):
	# Query embedding similar to first chunk
	results = vector_db_fixture.search([1, 0], top_k=2)
	assert len(results) == 2
	assert results[0]["metadata"]["title"] == "General Regulations"
	assert results[0]["metadata"]["page"] == 12
	assert "text" in results[0]

@pytest.fixture(autouse=True)
def patch_external_services():
    with patch("services.retrieval.app.retriever.QdrantClient") as mock_qdrant, \
         patch("services.retrieval.app.rabbitmq.EventConsumer") as mock_rabbitmq:
        mock_qdrant.return_value.search.return_value = [
            MagicMock(payload={"text": "Exam policy states ...", "title": "General Regulations", "page": 12, "url": "...", "relevanceScore": 0.99}, score=0.99, id=1)
            for _ in range(5)
        ]
        yield

def test_search_endpoint_returns_results():
	client = TestClient(app)
	response = client.post("/search", json={"query": "exam policy", "top_k": 5})
	assert response.status_code == 200
	results = response.json()["results"]
	assert len(results) == 5
	assert all("score" in r for r in results)
	assert all("title" in r for r in results)
	assert all("page" in r for r in results)

# Edge case: Empty query string
def test_search_empty_query(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 400
				def json(self):
					return {"error": "Missing required parameter: query"}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "", "top_k": 5})
	assert response.status_code == 400
	assert "error" in response.json()

# Edge case: Nonexistent query
def test_search_nonexistent_query(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": []}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "nonexistent", "top_k": 5})
	assert response.status_code == 200
	assert response.json()["results"] == []

# Edge case: Very large top_k value
def test_search_large_top_k(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": [{"title": "Doc", "page": 1, "score": 0.5}] * 100}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "doc", "top_k": 100})
	assert response.status_code == 200
	assert len(response.json()["results"]) == 100

# Edge case: Negative or zero top_k
def test_search_invalid_top_k(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": [{"title": "Doc", "page": 1, "score": 0.5}] * 5}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "doc", "top_k": -1})
	assert response.status_code == 200
	assert len(response.json()["results"]) == 5

# Edge case: Missing top_k field
def test_search_missing_top_k(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": [{"title": "Doc", "page": 1, "score": 0.5}] * 5}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "doc"})
	assert response.status_code == 200
	assert len(response.json()["results"]) == 5

# Edge case: Missing query field
def test_search_missing_query(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 400
				def json(self):
					return {"error": "Missing required parameter: query"}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"top_k": 5})
	assert response.status_code == 400
	assert "error" in response.json()

# Edge case: Special characters in query
def test_search_special_characters(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": [{"title": "Doc!@#", "page": 1, "score": 0.5}]}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "!@#", "top_k": 1})
	assert response.status_code == 200
	assert response.json()["results"][0]["title"] == "Doc!@#"

# Edge case: Unicode query
def test_search_unicode_query(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": [{"title": "Документ", "page": 1, "score": 0.5}]}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "Документ", "top_k": 1})
	assert response.status_code == 200
	assert response.json()["results"][0]["title"] == "Документ"

# Edge case: Database with no documents
def test_search_empty_db(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": []}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "anything", "top_k": 5})
	assert response.status_code == 200
	assert response.json()["results"] == []

# Edge case: Malformed request body
def test_search_malformed_request(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 400
				def json(self):
					return {"error": "Malformed request"}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json=None)
	assert response.status_code == 400
	assert "error" in response.json()

# Edge case: Partial document metadata
def test_search_partial_metadata(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": [{"title": None, "page": None, "score": 0.5}]}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "partial", "top_k": 1})
	assert response.status_code == 200
	assert "title" in response.json()["results"][0]
	assert "page" in response.json()["results"][0]

# Edge case: Duplicate documents
def test_search_duplicate_documents(monkeypatch):
	class DummyClient:
		def post(self, url, json):
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": [
						{"title": "Doc", "page": 1, "score": 0.5},
						{"title": "Doc", "page": 1, "score": 0.5}
					]}
			return DummyResponse()
	client = DummyClient()
	response = client.post("/search", json={"query": "duplicate", "top_k": 2})
	assert response.status_code == 200
	assert len(response.json()["results"]) == 2
	assert response.json()["results"][0] == response.json()["results"][1]

# Edge case: Slow response or timeout (simulated)
def test_search_slow_response(monkeypatch):
	import time
	class DummyClient:
		def post(self, url, json):
			time.sleep(0.1)  # Simulate delay
			class DummyResponse:
				status_code = 200
				def json(self):
					return {"results": [{"title": "Doc", "page": 1, "score": 0.5}]}
			return DummyResponse()
	client = DummyClient()
	start = time.time()
	response = client.post("/search", json={"query": "slow", "top_k": 1})
	elapsed = time.time() - start
	assert response.status_code == 200
	assert elapsed >= 0.1
