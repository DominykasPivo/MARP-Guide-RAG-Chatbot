"""
End-to-end tests for chat service flow.

Tests the complete chat workflow including:
- Query processing
- Retrieval integration
- Response generation
"""

import pytest


class TestChatServiceFlow:
    """Test chat service end-to-end flow."""

    def test_chat_health(self, chat_client):
        """Test chat service is healthy."""
        response = chat_client.health()

        assert response.status_code == 200
        assert response.json()["status"] in ["healthy", "ok"]

    @pytest.mark.skip(reason="Requires OPENAI_API_KEY and indexed documents")
    def test_chat_query_with_retrieval(self, chat_client, authenticated_user):
        """Test complete chat flow with retrieval."""
        # Send a query
        response = chat_client.post(
            "/chat",
            json={"query": "What is MARP?"},
            headers={"user-id": str(authenticated_user["user_id"])},
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "citations" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    @pytest.mark.skip(reason="Requires OPENAI_API_KEY")
    def test_chat_query_without_user_id(self, chat_client):
        """Test chat can work without user authentication."""
        response = chat_client.post("/chat", json={"query": "What is MARP?"})

        # Should either work or return appropriate error
        assert response.status_code in [200, 401, 400]

    def test_chat_invalid_request(self, chat_client):
        """Test chat with invalid request body."""
        response = chat_client.post("/chat", json={})

        assert response.status_code in [400, 422]  # Bad request or validation error


class TestRetrievalServiceFlow:
    """Test retrieval service end-to-end flow."""

    def test_retrieval_health(self, retrieval_client):
        """Test retrieval service is healthy."""
        response = retrieval_client.health()

        assert response.status_code == 200
        assert response.json()["status"] in ["healthy", "ok"]

    @pytest.mark.skip(reason="Requires indexed documents")
    def test_search_documents(self, retrieval_client):
        """Test document search via retrieval service."""
        response = retrieval_client.post(
            "/search", json={"query": "MARP guidelines", "top_k": 5}
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_empty_query(self, retrieval_client):
        """Test search with empty query."""
        response = retrieval_client.post("/search", json={"query": "", "top_k": 5})

        # Should handle gracefully
        assert response.status_code in [200, 400]


class TestChatRetrievalIntegration:
    """Test integration between chat and retrieval services."""

    @pytest.mark.skip(reason="Requires full system setup with documents and API keys")
    def test_end_to_end_chat_with_context(
        self, chat_client, retrieval_client, authenticated_user
    ):
        """
        Test complete chat flow with retrieval:
        1. Search for relevant documents
        2. Generate answer with context
        3. Verify citations are included
        """
        user_id = authenticated_user["user_id"]
        query = "What are the key principles of MARP?"

        # 1. Verify retrieval returns results
        response = retrieval_client.post("/search", json={"query": query, "top_k": 5})

        assert response.status_code == 200
        search_results = response.json()
        assert len(search_results.get("results", [])) > 0

        # 2. Send query to chat service
        response = chat_client.post(
            "/chat", json={"query": query}, headers={"user-id": str(user_id)}
        )

        assert response.status_code == 200
        chat_response = response.json()

        # 3. Verify response quality
        assert "answer" in chat_response
        assert len(chat_response["answer"]) > 0
        assert "citations" in chat_response
        assert len(chat_response["citations"]) > 0

        # 4. Verify answer is relevant (basic check)
        assert any(
            keyword in chat_response["answer"].lower()
            for keyword in ["marp", "principle", "guideline"]
        )


class TestChatWithAuthentication:
    """Test chat service with user authentication."""

    @pytest.mark.skip(reason="Requires OPENAI_API_KEY")
    def test_chat_saves_history(self, chat_client, auth_client, authenticated_user):
        """Test that chat queries are saved to user history."""
        user_id = authenticated_user["user_id"]

        # Send a chat query
        response = chat_client.post(
            "/chat",
            json={"query": "Test query for history"},
            headers={"user-id": str(user_id)},
        )

        assert response.status_code == 200

        # Check history in auth service
        response = auth_client.get("/history", headers={"user-id": str(user_id)})

        assert response.status_code == 200
        history = response.json()["history"]
        assert len(history) > 0
        assert any("test query" in msg["content"].lower() for msg in history)


class TestServiceCommunication:
    """Test communication between services."""

    def test_all_chat_services_healthy(self, chat_client, retrieval_client):
        """Verify all services needed for chat are running."""
        # Chat service
        response = chat_client.health()
        assert response.status_code == 200

        # Retrieval service
        response = retrieval_client.health()
        assert response.status_code == 200

    @pytest.mark.skip(reason="Requires message broker inspection")
    def test_event_publishing(self, chat_client):
        """Test that chat service publishes events to RabbitMQ."""
        # This would require inspecting RabbitMQ queues
        # to verify events are being published
        pass
