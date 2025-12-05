"""
Unit tests for the retrieval service FastAPI application.

Target: services/retrieval/app/app.py
Coverage: 87 statements at 0%

This file tests:
- FastAPI endpoints (/search, /query, /health, /debug/vector-store)
- Search functionality
- Error handling
"""

import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

# Mock the relative imports BEFORE importing app.py
if not TYPE_CHECKING:
    sys.modules["retrieval"] = Mock()
    sys.modules["retrieval_events"] = Mock()
    # Configure the mocks
    sys.modules["retrieval"].RetrievalService = Mock()  # type: ignore[attr-defined]
    sys.modules["retrieval_events"].publish_event = Mock()  # type: ignore[attr-defined]


class TestRetrievalAppEndpoints:
    """Test FastAPI endpoints in retrieval service."""

    def test_health_endpoint(self):
        """Test GET /health returns healthy status."""
        from services.retrieval.app.app import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "retrieval"
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_search_endpoint_success(self):
        """Test POST /search returns search results."""
        from services.retrieval.app.app import app, service

        # Mock retriever
        mock_retriever = Mock()
        mock_chunks = [
            {
                "text": "Test chunk 1",
                "title": "Test Doc",
                "page": 1,
                "url": "http://example.com",
                "relevanceScore": 0.95,
            },
            {
                "text": "Test chunk 2",
                "title": "Test Doc",
                "page": 2,
                "url": "http://example.com",
                "relevanceScore": 0.85,
            },
        ]
        mock_retriever.search.return_value = mock_chunks
        service._ensure_retriever = Mock(return_value=mock_retriever)

        client = TestClient(app)
        response = client.post("/search", json={"query": "test query", "top_k": 5})

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert len(data["results"]) == 2
        assert data["results"][0]["score"] == 0.95

    def test_search_endpoint_missing_query(self):
        """Test POST /search handles missing query parameter."""
        from services.retrieval.app.app import app

        client = TestClient(app)
        response = client.post("/search", json={"query": "", "top_k": 5})

        assert response.status_code == 400
        assert "Missing required parameter: query" in response.json()["error"]

    def test_search_endpoint_invalid_top_k(self):
        """Test POST /search validates top_k parameter."""
        from services.retrieval.app.app import app, service

        # Mock retriever
        mock_retriever = Mock()
        mock_retriever.search.return_value = []
        service._ensure_retriever = Mock(return_value=mock_retriever)

        client = TestClient(app)
        # Test with invalid top_k (should default to 5)
        response = client.post("/search", json={"query": "test", "top_k": 200})

        assert response.status_code == 200
        # Should have called search with default top_k=5
        mock_retriever.search.assert_called_with("test", 5)

    def test_search_endpoint_error(self):
        """Test POST /search handles search errors."""
        from services.retrieval.app.app import app, service

        # Mock retriever to raise exception
        service._ensure_retriever = Mock(side_effect=Exception("Search failed"))

        client = TestClient(app)
        response = client.post("/search", json={"query": "test query", "top_k": 5})

        assert response.status_code == 500
        assert "Search failed" in response.json()["error"]

    def test_query_endpoint_success(self):
        """Test POST /query returns search results."""
        from services.retrieval.app.app import app, service

        # Mock retriever
        mock_retriever = Mock()
        mock_chunks = [
            {
                "text": "Query result 1",
                "title": "Doc Title",
                "page": 3,
                "url": "http://test.com",
            }
        ]
        mock_retriever.search.return_value = mock_chunks
        service._ensure_retriever = Mock(return_value=mock_retriever)

        client = TestClient(app)
        response = client.post("/query", json={"query": "test query", "top_k": 3})

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert len(data["chunks"]) == 1
        assert data["chunks"][0]["text"] == "Query result 1"

    def test_query_endpoint_missing_query(self):
        """Test POST /query handles missing query parameter."""
        from services.retrieval.app.app import app

        client = TestClient(app)
        response = client.post("/query", json={"top_k": 5})

        assert response.status_code == 400
        assert "Query is required" in response.json()["error"]

    def test_query_endpoint_no_data(self):
        """Test POST /query handles missing request body."""
        from services.retrieval.app.app import app

        client = TestClient(app)
        # Empty JSON body - should check for "Request must include JSON data"
        response = client.post("/query", json={})

        assert response.status_code == 400
        # The actual error message checks if data is truthy (empty dict is falsy)
        assert "Request must include JSON data" in response.json()["error"]

    def test_query_endpoint_error(self):
        """Test POST /query handles query errors."""
        from services.retrieval.app.app import app, service

        # Mock retriever to raise exception
        service._ensure_retriever = Mock(side_effect=Exception("Query failed"))

        client = TestClient(app)
        response = client.post("/query", json={"query": "test"})

        assert response.status_code == 500
        assert "Query failed" in response.json()["error"]

    @patch("services.retrieval.app.app.QdrantClient")
    def test_debug_vector_store_success(self, mock_qdrant_client):
        """Test GET /debug/vector-store returns collection info."""
        from services.retrieval.app.app import app, service

        # Mock service attributes
        service.qdrant_host = "localhost"
        service.qdrant_port = 6333
        service.collection_name = "chunks"
        service.embedding_model = "test-model"
        service._ensure_retriever = Mock()

        # Mock Qdrant client
        mock_client_instance = Mock()
        mock_collection_info = {"points_count": 100}
        mock_client_instance.get_collection.return_value = mock_collection_info

        # Mock scroll to return sample points
        mock_point = Mock()
        mock_point.get = Mock(
            side_effect=lambda key, default=None: {
                "id": "point-1",
                "payload": {"text": "Sample text"},
                "vector": [0.1, 0.2, 0.3] * 100,
            }.get(key, default)
        )
        mock_client_instance.scroll.return_value = ([mock_point], None)

        mock_qdrant_client.return_value = mock_client_instance

        client = TestClient(app)
        response = client.get("/debug/vector-store")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["total_points"] == 100
        assert data["has_points"] is True

    @patch("services.retrieval.app.app.QdrantClient")
    def test_debug_vector_store_empty(self, mock_qdrant_client):
        """Test GET /debug/vector-store handles empty collection."""
        from services.retrieval.app.app import app, service

        # Mock service attributes
        service.qdrant_host = "localhost"
        service.qdrant_port = 6333
        service.collection_name = "chunks"
        service.embedding_model = "test-model"
        service._ensure_retriever = Mock()

        # Mock Qdrant client with empty collection
        mock_client_instance = Mock()
        mock_collection_info = {"points_count": 0}
        mock_client_instance.get_collection.return_value = mock_collection_info

        mock_qdrant_client.return_value = mock_client_instance

        client = TestClient(app)
        response = client.get("/debug/vector-store")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "empty"
        assert data["total_points"] == 0
        assert data["has_points"] is False

    @patch("services.retrieval.app.app.QdrantClient")
    def test_debug_vector_store_error(self, mock_qdrant_client):
        """Test GET /debug/vector-store handles errors."""
        from services.retrieval.app.app import app, service

        # Mock service to raise exception
        service._ensure_retriever = Mock(side_effect=Exception("Connection failed"))

        client = TestClient(app)
        response = client.get("/debug/vector-store")

        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
        assert "Connection failed" in data["error"]
