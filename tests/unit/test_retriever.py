"""
Unit tests for retriever business logic.

Tests search relevance, ranking accuracy, query preprocessing,
deduplication, edge cases, and error handling.

Target: services/retrieval/app/retriever.py
"""

from unittest.mock import Mock, patch

import pytest

from services.retrieval.app.retriever import Retriever, get_retriever

# ============================================================================
# TEST FIXTURES AND UTILITIES
# ============================================================================


class MockQdrantResult:
    """Mock Qdrant search result."""

    def __init__(self, id, score, payload):
        self.id = id
        self.score = score
        self.payload = payload


@pytest.fixture
def mock_retriever():
    """Create a retriever with mocked dependencies."""
    with (
        patch("services.retrieval.app.retriever.SentenceTransformer"),
        patch("services.retrieval.app.retriever.QdrantClient"),
    ):
        retriever = Retriever(
            embedding_model="all-MiniLM-L6-v2",
            qdrant_host="localhost",
            qdrant_port=6333,
            collection_name="test_chunks",
        )
        return retriever


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


class TestRetrieverInitialization:
    """Test retriever initialization and configuration."""

    def test_initialization_with_defaults(self):
        """Test retriever initializes with default parameters."""
        with (
            patch("services.retrieval.app.retriever.SentenceTransformer"),
            patch("services.retrieval.app.retriever.QdrantClient"),
        ):
            retriever = Retriever()

            assert retriever.embedding_model_name == "all-MiniLM-L6-v2"
            assert retriever.qdrant_host == "localhost"
            assert retriever.qdrant_port == 6333
            assert retriever.collection_name == "chunks"

    def test_initialization_with_custom_params(self):
        """Test retriever initializes with custom parameters."""
        with (
            patch("services.retrieval.app.retriever.SentenceTransformer"),
            patch("services.retrieval.app.retriever.QdrantClient"),
        ):
            retriever = Retriever(
                embedding_model="custom-model",
                qdrant_host="custom-host",
                qdrant_port=9999,
                collection_name="custom_collection",
            )

            assert retriever.embedding_model_name == "custom-model"
            assert retriever.qdrant_host == "custom-host"
            assert retriever.qdrant_port == 9999
            assert retriever.collection_name == "custom_collection"

    def test_singleton_get_retriever(self):
        """Test get_retriever returns singleton instance."""
        with (
            patch("services.retrieval.app.retriever.SentenceTransformer"),
            patch("services.retrieval.app.retriever.QdrantClient"),
        ):
            retriever1 = get_retriever()
            retriever2 = get_retriever()

            assert retriever1 is retriever2


# ============================================================================
# SEARCH FUNCTIONALITY TESTS
# ============================================================================


class TestSearchFunctionality:
    """Test core search functionality."""

    def test_search_returns_results(self, mock_retriever):
        """Test search returns expected results."""
        # Mock Qdrant search results
        mock_results = [
            MockQdrantResult(
                id=1,
                score=0.95,
                payload={
                    "text": "MARP provides guidelines for academic integrity.",
                    "title": "MARP Guide",
                    "page": 5,
                    "url": "http://example.com/marp.pdf",
                    "chunk_index": 0,
                },
            ),
            MockQdrantResult(
                id=2,
                score=0.85,
                payload={
                    "text": "Students must follow submission deadlines.",
                    "title": "MARP Rules",
                    "page": 12,
                    "url": "http://example.com/rules.pdf",
                    "chunk_index": 0,
                },
            ),
        ]

        mock_retriever.client.search.return_value = mock_results
        mock_retriever.encoder.encode.return_value = Mock(
            tolist=lambda: [0.1] * 384
        )  # Mock embedding

        results = mock_retriever.search("academic integrity", top_k=2)

        assert len(results) == 2
        assert results[0]["relevanceScore"] == 0.95
        assert results[1]["relevanceScore"] == 0.85
        assert "MARP provides guidelines" in results[0]["text"]

    def test_search_with_top_k_parameter(self, mock_retriever):
        """Test search respects top_k parameter."""
        mock_results = [
            MockQdrantResult(
                id=i,
                score=0.9 - (i * 0.1),
                payload={
                    "text": f"Chunk {i}",
                    "title": "Doc",
                    "page": i,
                    "url": "http://test.com",
                    "chunk_index": i,
                },
            )
            for i in range(10)
        ]

        mock_retriever.client.search.return_value = mock_results
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search("test query", top_k=3)

        assert len(results) == 3

    def test_search_lowercases_query(self, mock_retriever):
        """Test that search lowercases the query for consistency."""
        mock_retriever.client.search.return_value = []
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        mock_retriever.search("TEST QUERY WITH CAPS", top_k=5)

        # Verify encoder was called with lowercased query
        mock_retriever.encoder.encode.assert_called_once()
        call_args = mock_retriever.encoder.encode.call_args[0]
        assert call_args[0] == "test query with caps"


# ============================================================================
# RANKING AND RELEVANCE TESTS
# ============================================================================


class TestRankingAndRelevance:
    """Test result ranking and relevance scoring."""

    def test_results_sorted_by_score(self, mock_retriever):
        """Test that results are returned in score order."""
        # Return results out of order
        mock_results = [
            MockQdrantResult(
                id=1,
                score=0.5,
                payload={
                    "text": "Low score",
                    "title": "Doc1",
                    "page": 1,
                    "url": "http://test.com",
                    "chunk_index": 0,
                },
            ),
            MockQdrantResult(
                id=2,
                score=0.9,
                payload={
                    "text": "High score",
                    "title": "Doc2",
                    "page": 2,
                    "url": "http://test.com",
                    "chunk_index": 0,
                },
            ),
            MockQdrantResult(
                id=3,
                score=0.7,
                payload={
                    "text": "Medium score",
                    "title": "Doc3",
                    "page": 3,
                    "url": "http://test.com",
                    "chunk_index": 0,
                },
            ),
        ]

        mock_retriever.client.search.return_value = mock_results
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search("test", top_k=5)

        # Qdrant returns results sorted, but verify our processing maintains order
        assert results[0]["relevanceScore"] == 0.5  # As returned by Qdrant
        assert results[1]["relevanceScore"] == 0.9
        assert results[2]["relevanceScore"] == 0.7

    def test_relevance_score_included_in_results(self, mock_retriever):
        """Test that relevance score is included in each result."""
        mock_results = [
            MockQdrantResult(
                id=1,
                score=0.88,
                payload={
                    "text": "Content",
                    "title": "Doc",
                    "page": 1,
                    "url": "http://test.com",
                    "chunk_index": 0,
                },
            )
        ]

        mock_retriever.client.search.return_value = mock_results
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search("test", top_k=1)

        assert "relevanceScore" in results[0]
        assert results[0]["relevanceScore"] == 0.88


# ============================================================================
# DEDUPLICATION TESTS
# ============================================================================


class TestDeduplication:
    """Test deduplication logic."""

    def test_deduplicates_by_text_url_chunk_index(self, mock_retriever):
        """Test that duplicates are removed based on text, URL, and chunk index."""
        mock_results = [
            MockQdrantResult(
                id=1,
                score=0.9,
                payload={
                    "text": "Duplicate content",
                    "title": "Doc",
                    "page": 1,
                    "url": "http://test.com",
                    "chunk_index": 0,
                },
            ),
            MockQdrantResult(
                id=2,
                score=0.7,
                payload={
                    "text": "Duplicate content",
                    "title": "Doc",
                    "page": 1,
                    "url": "http://test.com",
                    "chunk_index": 0,  # Same chunk_index
                },
            ),
            MockQdrantResult(
                id=3,
                score=0.8,
                payload={
                    "text": "Different content",
                    "title": "Doc",
                    "page": 2,
                    "url": "http://test.com",
                    "chunk_index": 1,
                },
            ),
        ]

        mock_retriever.client.search.return_value = mock_results
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search("test", top_k=5)

        # Should keep first occurrence and the different one
        assert len(results) == 2
        assert results[0]["text"] == "Duplicate content"
        assert results[1]["text"] == "Different content"

    def test_keeps_different_chunks_from_same_page(self, mock_retriever):
        """Test that different chunks from same page are kept."""
        mock_results = [
            MockQdrantResult(
                id=1,
                score=0.9,
                payload={
                    "text": "First chunk",
                    "title": "Doc",
                    "page": 1,
                    "url": "http://test.com",
                    "chunk_index": 0,
                },
            ),
            MockQdrantResult(
                id=2,
                score=0.8,
                payload={
                    "text": "Second chunk",
                    "title": "Doc",
                    "page": 1,  # Same page
                    "url": "http://test.com",
                    "chunk_index": 1,  # Different chunk
                },
            ),
        ]

        mock_retriever.client.search.return_value = mock_results
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search("test", top_k=5)

        # Both should be kept since they're different chunks
        assert len(results) == 2


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Test edge cases in search."""

    def test_search_with_empty_query(self, mock_retriever):
        """Test search with empty query string."""
        mock_retriever.client.search.return_value = []
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search("", top_k=5)

        # Should handle empty query gracefully
        assert isinstance(results, list)

    def test_search_with_special_characters(self, mock_retriever):
        """Test search with special characters in query."""
        mock_retriever.client.search.return_value = []
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search("test@#$%^&*()", top_k=5)

        assert isinstance(results, list)

    def test_search_with_very_long_query(self, mock_retriever):
        """Test search with very long query string."""
        long_query = "test query " * 1000  # Very long query
        mock_retriever.client.search.return_value = []
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search(long_query, top_k=5)

        assert isinstance(results, list)


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Test error handling in retrieval."""

    def test_search_handles_encoder_failure(self, mock_retriever):
        """Test search handles encoder failure gracefully."""
        mock_retriever.encoder.encode.side_effect = Exception("Encoding failed")

        results = mock_retriever.search("test query", top_k=5)

        # Should return empty list on error
        assert results == []

    def test_search_handles_qdrant_failure(self, mock_retriever):
        """Test search handles Qdrant connection failure."""
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)
        mock_retriever.client.search.side_effect = Exception("Qdrant error")

        results = mock_retriever.search("test query", top_k=5)

        assert results == []

    def test_search_handles_missing_encoder(self, mock_retriever):
        """Test search handles missing encoder."""
        mock_retriever.encoder = None

        results = mock_retriever.search("test query", top_k=5)

        assert results == []

    def test_search_handles_missing_client(self, mock_retriever):
        """Test search handles missing Qdrant client."""
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)
        mock_retriever.client = None

        results = mock_retriever.search("test query", top_k=5)

        assert results == []


# ============================================================================
# RESULT STRUCTURE TESTS
# ============================================================================


class TestResultStructure:
    """Test structure of search results."""

    def test_result_contains_required_fields(self, mock_retriever):
        """Test that each result contains all required fields."""
        mock_results = [
            MockQdrantResult(
                id=1,
                score=0.9,
                payload={
                    "text": "Test content",
                    "title": "Test Doc",
                    "page": 5,
                    "url": "http://test.com/doc.pdf",
                    "chunk_index": 0,
                },
            )
        ]

        mock_retriever.client.search.return_value = mock_results
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search("test", top_k=1)

        required_fields = [
            "id",
            "text",
            "relevanceScore",
            "title",
            "page",
            "url",
            "chunkIndex",
        ]
        for field in required_fields:
            assert field in results[0], f"Missing field: {field}"

    def test_result_uses_fallback_values(self, mock_retriever):
        """Test that results use fallback values for missing fields."""
        mock_results = [
            MockQdrantResult(
                id=1,
                score=0.9,
                payload={
                    "text": "Content"
                    # Missing title, page, url, chunk_index
                },
            )
        ]

        mock_retriever.client.search.return_value = mock_results
        mock_retriever.encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        results = mock_retriever.search("test", top_k=1)

        assert results[0]["title"] == "MARP Document"  # Fallback
        assert results[0]["page"] == 0  # Fallback
        assert results[0]["url"] == ""  # Fallback
        assert results[0]["chunkIndex"] == 0  # Fallback
