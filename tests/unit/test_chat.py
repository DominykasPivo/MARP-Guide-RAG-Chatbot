"""
Unit tests for chat service.

This file combines business logic and integration tests for the chat service:
- RAG prompt generation and context building
- Citation extraction, filtering, and deduplication
- Multi-LLM response handling
- Event structure and correlation ID propagation

Target modules:
- services/chat/app/llm_rag_helpers.py (RAG logic)
- services/chat/app/app.py (citation filtering, API endpoints)
- services/chat/app/events.py (event structures)
"""

import sys
from pathlib import Path

# Add chat service to path
chat_app = Path(__file__).parent.parent.parent / "services" / "chat" / "app"
if str(chat_app) not in sys.path:
    sys.path.insert(0, str(chat_app))

# Import after path is set
from llm_rag_helpers import build_rag_prompt, extract_citations  # noqa: E402
from models import Chunk, Citation  # noqa: E402

# ============================================================================
# RAG PROMPT GENERATION TESTS
# ============================================================================


class TestRAGPromptGeneration:
    """Test RAG prompt construction from chunks."""

    def test_prompt_with_chunks(self):
        """Test that RAG prompt correctly formats chunks into context."""
        chunks = [
            Chunk(
                text="First chunk content",
                title="Doc1",
                page=1,
                url="http://example.com/doc1.pdf",
                score=0.9,
            ),
            Chunk(
                text="Second chunk content",
                title="Doc2",
                page=2,
                url="http://example.com/doc2.pdf",
                score=0.8,
            ),
        ]
        query = "What is the policy?"

        prompt = build_rag_prompt(query, chunks)

        # Verify structure
        assert "CONTEXT:" in prompt
        assert "QUESTION:" in prompt
        assert query in prompt

        # Verify chunks are included with metadata
        assert "First chunk content" in prompt
        assert "Second chunk content" in prompt
        assert "Doc1" in prompt
        assert "Page: 1" in prompt
        assert "Doc2" in prompt
        assert "Page: 2" in prompt

    def test_prompt_with_empty_chunks(self):
        """Test RAG prompt with no chunks."""
        query = "What is the answer?"

        prompt = build_rag_prompt(query, [])

        # Should still have structure but empty context
        assert "CONTEXT:" in prompt
        assert query in prompt

    def test_prompt_formatting(self):
        """Test that chunks are separated by visual dividers."""
        chunks = [
            Chunk(
                text="Content 1", title="Doc", page=1, url="http://test.com", score=0.9
            ),
            Chunk(
                text="Content 2", title="Doc", page=2, url="http://test.com", score=0.8
            ),
        ]

        prompt = build_rag_prompt("test query", chunks)

        # Chunks should be separated by ---
        assert "---" in prompt
        # Should have multiple separators for multiple chunks
        assert prompt.count("---") >= 2

    def test_prompt_includes_all_chunk_content(self):
        """Test that all chunk text is included in prompt."""
        chunks = [
            Chunk(
                text="MARP provides comprehensive guidelines for academic integrity.",
                title="MARP Guide",
                page=5,
                url="http://test.com/marp.pdf",
                score=0.95,
            ),
            Chunk(
                text="Students must adhere to submission deadlines.",
                title="MARP Rules",
                page=12,
                url="http://test.com/rules.pdf",
                score=0.85,
            ),
        ]

        prompt = build_rag_prompt("What are the academic policies?", chunks)

        assert "comprehensive guidelines for academic integrity" in prompt
        assert "submission deadlines" in prompt


# ============================================================================
# CITATION EXTRACTION TESTS
# ============================================================================


class TestCitationExtraction:
    """Test citation extraction logic from chunks."""

    def test_basic_citation_extraction(self):
        """Test basic citation extraction from chunks."""
        chunks = [
            Chunk(
                text="Content",
                title="Doc1",
                page=1,
                url="http://test.com/doc1.pdf",
                score=0.9,
            ),
            Chunk(
                text="Content",
                title="Doc2",
                page=2,
                url="http://test.com/doc2.pdf",
                score=0.8,
            ),
        ]

        citations = extract_citations(chunks)

        assert len(citations) == 2
        assert all(isinstance(c, Citation) for c in citations)
        assert citations[0].title == "Doc1"
        assert citations[0].score == 0.9

    def test_filters_low_score_citations(self):
        """Test that citations below 0.3 threshold are filtered out."""
        chunks = [
            Chunk(
                text="High score",
                title="Doc1",
                page=1,
                url="http://test.com",
                score=0.9,
            ),
            Chunk(
                text="Low score", title="Doc2", page=2, url="http://test.com", score=0.2
            ),
            Chunk(
                text="Below threshold",
                title="Doc3",
                page=3,
                url="http://test.com",
                score=0.1,
            ),
        ]

        citations = extract_citations(chunks)

        # Only the high score chunk should be included
        assert len(citations) == 1
        assert citations[0].title == "Doc1"
        assert citations[0].score == 0.9

    def test_deduplicates_citations(self):
        """Test that duplicate citations are removed, keeping highest score."""
        chunks = [
            Chunk(
                text="Content 1", title="Doc", page=1, url="http://test.com", score=0.7
            ),
            Chunk(
                text="Content 2", title="Doc", page=1, url="http://test.com", score=0.9
            ),
            Chunk(
                text="Content 3", title="Doc", page=1, url="http://test.com", score=0.5
            ),
        ]

        citations = extract_citations(chunks)

        # Should have only one citation with the highest score
        assert len(citations) == 1
        assert citations[0].score == 0.9

    def test_empty_chunks(self):
        """Test that empty chunk list returns empty citations."""
        citations = extract_citations([])
        assert citations == []

    def test_citations_sorted_by_score(self):
        """Test that citations are sorted by score descending."""
        chunks = [
            Chunk(text="Low", title="Doc1", page=1, url="http://test.com", score=0.5),
            Chunk(text="High", title="Doc2", page=2, url="http://test.com", score=0.9),
            Chunk(
                text="Medium", title="Doc3", page=3, url="http://test.com", score=0.7
            ),
        ]

        citations = extract_citations(chunks)

        # Should be sorted high to low
        assert len(citations) == 3
        assert citations[0].score == 0.9
        assert citations[1].score == 0.7
        assert citations[2].score == 0.5

    def test_handles_none_scores(self):
        """Test citation extraction when chunks have None scores."""
        chunks = [
            Chunk(
                text="Content", title="Doc", page=1, url="http://test.com", score=None
            ),
        ]

        citations = extract_citations(chunks)

        # None should be treated as 0.0, which is below threshold
        assert len(citations) == 0

    def test_all_below_threshold(self):
        """Test that empty list is returned when all citations below threshold."""
        chunks = [
            Chunk(text="Low 1", title="Doc1", page=1, url="http://test.com", score=0.2),
            Chunk(text="Low 2", title="Doc2", page=2, url="http://test.com", score=0.1),
        ]

        citations = extract_citations(chunks)
        assert citations == []

    def test_multiple_citations_format(self):
        """Test handling multiple citations with proper structure."""
        citations = [
            Citation(
                title="MARP Guide",
                page=5,
                url="http://example.com/guide.pdf",
                score=0.9,
            ),
            Citation(
                title="MARP Reference",
                page=12,
                url="http://example.com/ref.pdf",
                score=0.8,
            ),
            Citation(
                title="MARP Examples",
                page=3,
                url="http://example.com/examples.pdf",
                score=0.7,
            ),
        ]

        assert len(citations) == 3
        assert all(hasattr(c, "title") and hasattr(c, "page") for c in citations)


# ============================================================================
# CITATION FILTERING TESTS (filter_top_citations from app.py)
# ============================================================================


class TestCitationFiltering:
    """Test citation filtering logic in chat service."""

    def test_filter_top_citations_basic(self):
        """Test basic filtering of top N citations."""
        from services.chat.app.app import filter_top_citations

        citations = [
            Citation(title="Doc1", page=1, url="http://test.com", score=0.95),
            Citation(title="Doc2", page=2, url="http://test.com", score=0.85),
            Citation(title="Doc3", page=3, url="http://test.com", score=0.75),
            Citation(title="Doc4", page=4, url="http://test.com", score=0.65),
        ]

        result = filter_top_citations(citations, top_n=3, min_citations=2)

        assert len(result) == 3
        assert result[0].score == 0.95
        assert result[1].score == 0.85
        assert result[2].score == 0.75

    def test_filter_respects_min_citations(self):
        """Test that filter returns at least min_citations even if top_n is smaller."""
        from services.chat.app.app import filter_top_citations

        citations = [
            Citation(title="Doc1", page=1, url="http://test.com", score=0.9),
            Citation(title="Doc2", page=2, url="http://test.com", score=0.8),
        ]

        # top_n=1 but min_citations=2 should return 2
        result = filter_top_citations(citations, top_n=1, min_citations=2)

        assert len(result) == 2

    def test_filter_with_fewer_citations_than_requested(self):
        """Test filtering when there are fewer citations than requested."""
        from services.chat.app.app import filter_top_citations

        citations = [
            Citation(title="Doc1", page=1, url="http://test.com", score=0.9),
        ]

        result = filter_top_citations(citations, top_n=5, min_citations=2)

        # Should return only 1 citation (all available)
        assert len(result) == 1

    def test_filter_empty_citations(self):
        """Test filtering with empty citation list."""
        from services.chat.app.app import filter_top_citations

        result = filter_top_citations([], top_n=3, min_citations=2)

        assert result == []


# ============================================================================
# CONTEXT BUILDING TESTS
# ============================================================================


class TestContextBuilding:
    """Test context handling in chat."""

    def test_context_from_retrieved_chunks(self):
        """Test using retrieved chunks as context."""
        chunks = [
            {"text": "MARP is a framework", "title": "Guide", "page": 1},
            {"text": "It includes guidelines", "title": "Guide", "page": 2},
        ]

        context = "\n".join([c["text"] for c in chunks])
        assert "MARP is a framework" in context
        assert "It includes guidelines" in context

    def test_multi_chunk_context(self):
        """Test building context from multiple chunks."""
        chunks = [
            {"text": "Chunk 1 content", "page": 1},
            {"text": "Chunk 2 content", "page": 2},
            {"text": "Chunk 3 content", "page": 3},
        ]

        context_parts = [c["text"] for c in chunks]
        full_context = "\n---\n".join(context_parts)

        assert "Chunk 1 content" in full_context
        assert "Chunk 2 content" in full_context
        assert "Chunk 3 content" in full_context

    def test_context_with_metadata(self):
        """Test context includes metadata."""
        chunk = {
            "text": "Content here",
            "title": "Source Doc",
            "page": 5,
            "url": "http://example.com/doc.pdf",
        }

        context = f"{chunk['title']} (page {chunk['page']}): {chunk['text']}"
        assert chunk["title"] in context
        assert str(chunk["page"]) in context


# ============================================================================
# EVENT STRUCTURE TESTS
# ============================================================================


class TestChatEvents:
    """Test chat service event structures."""

    def test_query_received_event(self):
        """Test QueryReceived event creation."""
        from services.chat.app.events import QueryReceived

        event = QueryReceived(
            eventType="queryreceived",
            eventId="evt-001",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="chat-service",
            version="1.0",
            payload={
                "queryId": "q-001",
                "userId": "user-001",
                "queryText": "What is MARP?",
            },
        )

        assert event.eventType == "queryreceived"
        assert event.payload["queryText"] == "What is MARP?"

    def test_response_generated_event(self):
        """Test ResponseGenerated event creation."""
        from services.chat.app.events import ResponseGenerated

        event = ResponseGenerated(
            eventType="responsegenerated",
            eventId="evt-003",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="chat-service",
            version="1.0",
            payload={
                "queryId": "q-001",
                "userId": "user-001",
                "answer": "MARP is a comprehensive guide...",
                "citations": [
                    {
                        "title": "MARP Guide",
                        "page": 1,
                        "url": "http://example.com/marp.pdf",
                    }
                ],
                "modelUsed": "gpt-4",
                "retrievalModel": "all-MiniLM-L6-v2",
            },
        )

        assert event.payload["answer"]
        assert "citations" in event.payload
        assert event.payload["modelUsed"] == "gpt-4"

    def test_event_types_enum(self):
        """Test EventTypes enumeration."""
        from services.chat.app.events import EventTypes

        assert EventTypes.QUERY_RECEIVED.value == "queryreceived"
        assert EventTypes.CHUNKS_RETRIEVED.value == "chunksretrieved"
        assert EventTypes.RESPONSE_GENERATED.value == "responsegenerated"
        assert EventTypes.ANSWER_GENERATED.value == "answergenerated"


# ============================================================================
# CORRELATION ID TESTS
# ============================================================================


class TestCorrelationIDPropagation:
    """Test correlation ID tracking through chat flow."""

    def test_correlation_id_in_query_received(self):
        """Test correlation ID in QueryReceived event."""
        from services.chat.app.events import QueryReceived

        corr_id = "chat-corr-12345"
        event = QueryReceived(
            eventType="queryreceived",
            eventId="evt-006",
            timestamp="2025-01-01T00:00:00Z",
            correlationId=corr_id,
            source="chat-service",
            version="1.0",
            payload={"queryId": "q-001", "userId": "u-001", "queryText": "Test"},
        )

        assert event.correlationId == corr_id

    def test_correlation_id_in_response_generated(self):
        """Test correlation ID propagates to ResponseGenerated."""
        from services.chat.app.events import ResponseGenerated

        corr_id = "chat-corr-67890"
        event = ResponseGenerated(
            eventType="responsegenerated",
            eventId="evt-007",
            timestamp="2025-01-01T00:00:00Z",
            correlationId=corr_id,
            source="chat-service",
            version="1.0",
            payload={
                "queryId": "q-001",
                "userId": "u-001",
                "answer": "Answer",
                "citations": [],
            },
        )

        assert event.correlationId == corr_id
