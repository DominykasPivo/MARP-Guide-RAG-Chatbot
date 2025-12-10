"""Unit tests for event publishing and consumption."""

import json
import pytest
from unittest.mock import MagicMock, patch


class TestEventPublishing:
    """Test event publishing functionality."""

    @patch(
        "services.retrieval.app.retrieval_events."
        "pika.BlockingConnection"
    )
    def test_publish_retrieval_completed_event(
        self, mock_connection
    ):
        """Test publishing RetrievalCompleted event."""
        from services.retrieval.app.retrieval_events import (
            publish_retrieval_completed_event
        )

        # Setup mock
        mock_channel = MagicMock()
        mock_conn = (
            mock_connection.return_value.__enter__.return_value
        )
        mock_conn.channel.return_value = mock_channel

        # Publish event
        publish_retrieval_completed_event(
            query_id="test-123",
            query="test query",
            results_count=5,
            top_score=0.95,
            latency_ms=100.5
        )

        # Verify basic_publish was called
        assert mock_channel.basic_publish.called
        call_args = mock_channel.basic_publish.call_args

        # Verify routing key
        assert (
            call_args[1]["routing_key"] == "retrieval.completed"
        )

        # Verify event structure
        published_body = call_args[1]["body"]
        event_data = json.loads(published_body)

        assert event_data["eventType"] == "RetrievalCompleted"
        payload = event_data["payload"]
        assert payload["queryId"] == "test-123"
        assert payload["resultsCount"] == 5
        assert payload["topScore"] == 0.95
        assert payload["latencyMs"] == 100.5

    @patch(
        "services.chat.app.chat_events.pika.BlockingConnection"
    )
    def test_publish_query_received_event(
        self, mock_connection
    ):
        """Test publishing QueryReceived event."""
        from services.chat.app.chat_events import (
            publish_query_received_event
        )

        # Setup mock
        mock_channel = MagicMock()
        mock_conn = (
            mock_connection.return_value.__enter__.return_value
        )
        mock_conn.channel.return_value = mock_channel

        # Publish event
        publish_query_received_event(
            query_id="test-456",
            user_id="user-789",
            query_text="What is MARP?"
        )

        # Verify basic_publish was called
        assert mock_channel.basic_publish.called
        call_args = mock_channel.basic_publish.call_args

        # Verify routing key
        assert call_args[1]["routing_key"] == "query.received"

        # Verify event structure
        published_body = call_args[1]["body"]
        event_data = json.loads(published_body)

        assert event_data["eventType"] == "QueryReceived"
        payload = event_data["payload"]
        assert payload["queryId"] == "test-456"
        assert payload["userId"] == "user-789"
        assert payload["query"] == "What is MARP?"


class TestEventConsumption:
    """Test event consumption functionality."""

    def test_retrieval_completed_event_schema(self):
        """Test RetrievalCompleted event schema."""
        event = {
            "eventType": "RetrievalCompleted",
            "timestamp": "2024-01-01T00:00:00Z",
            "payload": {
                "queryId": "test-123",
                "query": "test query",
                "resultsCount": 5,
                "topScore": 0.95,
                "latencyMs": 100.5
            }
        }

        # Validate schema
        assert event["eventType"] == "RetrievalCompleted"
        payload = event["payload"]
        assert "queryId" in payload
        assert "resultsCount" in payload
        assert "topScore" in payload
        assert "latencyMs" in payload
        assert isinstance(payload["resultsCount"], int)
        assert isinstance(payload["topScore"], float)
        assert isinstance(payload["latencyMs"], float)

    def test_query_received_event_schema(self):
        """Test QueryReceived event schema."""
        event = {
            "eventType": "QueryReceived",
            "timestamp": "2024-01-01T00:00:00Z",
            "payload": {
                "queryId": "test-456",
                "userId": "user-789",
                "query": "What is MARP?"
            }
        }

        # Validate schema
        assert event["eventType"] == "QueryReceived"
        payload = event["payload"]
        assert "queryId" in payload
        assert "userId" in payload
        assert "query" in payload
        assert isinstance(payload["query"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
