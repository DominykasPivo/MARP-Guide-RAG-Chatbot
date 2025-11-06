import pytest
from unittest.mock import Mock, patch

from retriever import Retriever, get_retriever

class TestRetriever:
    
    @patch('retriever.VectorStore')
    @patch('retriever.SentenceTransformer')
    def test_retriever_initialization(self, mock_transformer, mock_vector_store):
        """Test Retriever initializes correctly"""
        retriever = Retriever()
        
        assert retriever.model is not None
        assert retriever.vector_store is not None
        mock_transformer.assert_called_once_with("all-MiniLM-L6-v2")
        mock_vector_store.assert_called_once()
    
    @patch('retriever.VectorStore')
    @patch('retriever.SentenceTransformer')
    def test_search_returns_formatted_results(self, mock_transformer, mock_vector_store):
        """Test search method returns properly formatted results"""
        mock_model = Mock()
        mock_model.encode.return_value = Mock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model
        
        mock_hit = Mock()
        mock_hit.payload = {
            "text": "Exceptional circumstances refer to unforeseen events...",
            "title": "MARP Guide - Chapter 2: Assessment",
            "page": 15,
            "url": "https://lancaster.ac.uk/marp.pdf#page=15"
        }
        mock_hit.score = 0.92
        
        mock_vs_instance = Mock()
        mock_vs_instance.search.return_value = [mock_hit]
        mock_vector_store.return_value = mock_vs_instance
        
        retriever = Retriever()
        results = retriever.search("What is exceptional circumstances?", top_k=5)
        
        assert len(results) == 1
        assert results[0]["text"] == "Exceptional circumstances refer to unforeseen events..."
        assert results[0]["title"] == "MARP Guide - Chapter 2: Assessment"
        assert results[0]["page"] == 15
        assert results[0]["score"] == 0.92
    
    @patch('retriever.VectorStore')
    @patch('retriever.SentenceTransformer')
    def test_search_multiple_results(self, mock_transformer, mock_vector_store):
        """Test search with multiple results"""
        mock_model = Mock()
        mock_model.encode.return_value = Mock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model
        
        mock_hits = []
        for i in range(3):
            mock_hit = Mock()
            mock_hit.payload = {
                "text": f"Sample text {i}",
                "title": f"Document {i}",
                "page": i + 1,
                "url": f"http://example.com/doc{i}.pdf"
            }
            mock_hit.score = 0.9 - (i * 0.1)
            mock_hits.append(mock_hit)
        
        mock_vs_instance = Mock()
        mock_vs_instance.search.return_value = mock_hits
        mock_vector_store.return_value = mock_vs_instance
        
        retriever = Retriever()
        results = retriever.search("test query", top_k=3)
        
        assert len(results) == 3
        assert results[0]["score"] == 0.9
        assert results[1]["score"] == 0.8
        assert results[2]["score"] == 0.7
    
    @patch('retriever.VectorStore')
    @patch('retriever.SentenceTransformer')
    def test_get_retriever_singleton(self, mock_transformer, mock_vector_store):
        """Test get_retriever returns same instance"""
        import retriever as retriever_module
        retriever_module._retriever = None
        
        retriever1 = get_retriever()
        retriever2 = get_retriever()
        
        assert retriever1 is retriever2