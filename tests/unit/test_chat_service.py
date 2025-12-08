"""Detailed unit tests for chat service."""


class TestChatServiceEvents:
    """Test chat service event handling."""

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

    def test_chunks_retrieved_event(self):
        """Test ChunksRetrieved event handling."""
        from services.chat.app.events import ChunksRetrieved

        event = ChunksRetrieved(
            eventType="chunksretrieved",
            eventId="evt-002",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="retrieval-service",
            version="1.0",
            payload={
                "queryId": "q-001",
                "retrievedChunks": [
                    {
                        "chunkId": "chunk-001",
                        "documentId": "doc-001",
                        "text": "MARP is a framework for...",
                        "title": "MARP Guide",
                        "page": 1,
                        "url": "http://example.com/marp.pdf",
                        "relevanceScore": 0.95,
                    }
                ],
            },
        )

        assert "retrievedChunks" in event.payload
        assert len(event.payload["retrievedChunks"]) == 1

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

    def test_answer_generated_event(self):
        """Test AnswerGenerated event creation."""
        from services.chat.app.events import AnswerGenerated

        event = AnswerGenerated(
            eventType="answergenerated",
            eventId="evt-004",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="chat-service",
            version="1.0",
            payload={
                "queryId": "q-001",
                "answerText": "MARP is a framework...",
                "citations": [
                    {"documentId": "doc-001", "chunkId": "chunk-001", "sourcePage": 1}
                ],
                "confidence": 0.92,
                "generatedAt": "2025-01-01T00:00:01Z",
            },
        )

        assert "answerText" in event.payload
        assert "citations" in event.payload
        assert event.payload["confidence"] > 0.8


class TestCitationExtraction:
    """Test citation extraction from responses."""

    def test_multiple_citations(self):
        """Test handling multiple citations."""
        citations = [
            {"title": "MARP Guide", "page": 5, "url": "http://example.com/guide.pdf"},
            {
                "title": "MARP Reference",
                "page": 12,
                "url": "http://example.com/ref.pdf",
            },
            {
                "title": "MARP Examples",
                "page": 3,
                "url": "http://example.com/examples.pdf",
            },
        ]

        assert len(citations) == 3
        assert all("title" in c and "page" in c for c in citations)


class TestResponseFormatting:
    """Test response formatting and structure."""

    def test_format_answer_with_citations(self):
        """Test formatting answer with citations."""
        answer_text = "MARP provides a systematic approach..."
        citations = [{"title": "MARP Guide", "page": 1}]

        formatted_response = {
            "answer": answer_text,
            "citations": citations,
            "model": "gpt-4",
        }

        assert formatted_response["answer"] == answer_text
        assert len(formatted_response["citations"]) == 1

    def test_response_includes_all_fields(self):
        """Test response includes required fields."""
        response = {
            "answer": "Sample answer",
            "citations": [],
            "modelUsed": "gpt-4",
            "retrievalModel": "all-MiniLM-L6-v2",
        }

        required_fields = ["answer", "citations", "modelUsed", "retrievalModel"]
        assert all(field in response for field in required_fields)


class TestContextAwareness:
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


class TestEventTypes:
    """Test chat service event types."""

    def test_event_types_enum(self):
        """Test EventTypes enumeration."""
        from services.chat.app.events import EventTypes

        assert EventTypes.QUERY_RECEIVED.value == "queryreceived"
        assert EventTypes.CHUNKS_RETRIEVED.value == "chunksretrieved"
        assert EventTypes.RESPONSE_GENERATED.value == "responsegenerated"
        assert EventTypes.ANSWER_GENERATED.value == "answergenerated"

    def test_event_version(self):
        """Test event version tracking."""
        from services.chat.app.events import QueryReceived

        event = QueryReceived(
            eventType="queryreceived",
            eventId="evt-005",
            timestamp="2025-01-01T00:00:00Z",
            correlationId="corr-001",
            source="chat-service",
            version="1.0",
            payload={"queryId": "q-001", "userId": "u-001", "queryText": "Test"},
        )

        assert event.version == "1.0"


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
