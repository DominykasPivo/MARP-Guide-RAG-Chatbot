import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app import app

client = TestClient(app)

class TestAPI:
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "retrieval"
    
    @patch('app.retriever')
    @patch('app.publish_event')
    def test_search_endpoint_success(self, mock_publish, mock_retriever):
        """Test search endpoint returns results"""
        mock_retriever.search.return_value = [
            {
                "text": "MARP regulations state that...",
                "title": "MARP Guide - Section 1",
                "page": 5,
                "url": "https://lancaster.ac.uk/marp.pdf#page=5",
                "score": 0.95
            },
            {
                "text": "Additional information about...",
                "title": "MARP Guide - Section 2",
                "page": 12,
                "url": "https://lancaster.ac.uk/marp.pdf#page=12",
                "score": 0.87
            }
        ]
        mock_publish.return_value = True
        
        response = client.post(
            "/search",
            json={"query": "What is MARP?", "top_k": 3}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is MARP?"
        assert len(data["results"]) == 2
        assert data["results"][0]["score"] == 0.95
        assert data["results"][0]["page"] == 5
        
        mock_retriever.search.assert_called_once_with("What is MARP?", 3)
        mock_publish.assert_called_once()
    
    @patch('app.retriever')
    @patch('app.publish_event')
    def test_search_endpoint_empty_results(self, mock_publish, mock_retriever):
        """Test search with no results"""
        mock_retriever.search.return_value = []
        mock_publish.return_value = True
        
        response = client.post(
            "/search",
            json={"query": "nonexistent query", "top_k": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 0
    
    @patch('app.retriever')
    def test_search_endpoint_error_handling(self, mock_retriever):
        """Test search endpoint handles errors"""
        mock_retriever.search.side_effect = Exception("Qdrant connection failed")
        
        response = client.post(
            "/search",
            json={"query": "test query", "top_k": 3}
        )
        
        assert response.status_code == 500
        assert "Qdrant connection failed" in response.json()["detail"]
    
    def test_search_endpoint_validation(self):
        """Test search endpoint validates input"""
        response = client.post(
            "/search",
            json={"top_k": 3}
        )
        
        assert response.status_code == 422
    
    def test_search_endpoint_default_top_k(self):
        """Test search uses default top_k value"""
        with patch('app.retriever') as mock_retriever, \
             patch('app.publish_event') as mock_publish:
            
            mock_retriever.search.return_value = []
            mock_publish.return_value = True
            
            response = client.post(
                "/search",
                json={"query": "test query"}
            )
            
            assert response.status_code == 200
            mock_retriever.search.assert_called_once_with("test query", 5)