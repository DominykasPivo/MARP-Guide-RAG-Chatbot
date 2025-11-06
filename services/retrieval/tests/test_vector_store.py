import pytest
from unittest.mock import Mock, patch

from vector_store import VectorStore

class TestVectorStore:
    
    @patch('vector_store.chromadb.HttpClient')  # ← Changed from QdrantClient
    def test_vector_store_initialization(self, mock_chroma):
        """Test VectorStore initializes correctly"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_client.get_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client
        
        vector_store = VectorStore()
        
        assert vector_store.collection_name == "marp_chunks"
        mock_chroma.assert_called_once()
    
    @patch('vector_store.chromadb.HttpClient')  # ← Changed
    def test_search_returns_results(self, mock_chroma):
        """Test search method returns formatted results"""
        mock_client = Mock()
        mock_collection = Mock()
        
        # Mock ChromaDB response format
        mock_collection.query.return_value = {
            'ids': [['id1']],
            'distances': [[0.05]],  # ChromaDB returns distance
            'metadatas': [[{
                "text": "Sample text about MARP regulations",
                "title": "MARP Guide - Section 2",
                "page": 15,
                "url": "https://example.com/marp.pdf#page=15"
            }]]
        }
        
        mock_client.get_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client
        
        vector_store = VectorStore()
        results = vector_store.search([0.1] * 384, limit=5)
        
        assert len(results) == 1
        assert results[0].score == 0.95  # 1 - 0.05
        mock_collection.query.assert_called_once()
    
    @patch('vector_store.chromadb.HttpClient')  # ← Changed
    def test_search_empty_results(self, mock_chroma):
        """Test search with no results"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [[]],
            'distances': [[]],
            'metadatas': [[]]
        }
        
        mock_client.get_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client
        
        vector_store = VectorStore()
        results = vector_store.search([0.1] * 384, limit=5)
        
        assert len(results) == 0