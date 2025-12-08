"""
Unit tests for RetrievalService class.

Target: services/retrieval/app/retrieval.py
Coverage: 106 statements at 0%
"""

import json
import sys
from unittest.mock import Mock

# Mock dependencies at module level
sys.modules["events"] = Mock()
sys.modules["retrieval_events"] = Mock()
sys.modules["retrieval_rabbitmq"] = Mock()
sys.modules["retriever"] = Mock()


class TestRetrievalService:
    """Test RetrievalService initialization and event handling."""

    def setup_method(self):
        """Reset mocks before each test."""
        sys.modules["retrieval_events"].reset_mock()
        sys.modules["retrieval_rabbitmq"].reset_mock()
        sys.modules["retriever"].reset_mock()

    def test_service_initialization(self):
        """Test RetrievalService initializes with correct parameters."""
        from services.retrieval.app.retrieval import RetrievalService

        service = RetrievalService(rabbitmq_host="rabbitmq")

        assert service.rabbitmq_host == "rabbitmq"
        assert service.consumer is None
        assert service.retriever is None
        assert service.collection_name == "chunks"

    def test_ensure_consumer_creates_new_consumer(self):
        """Test _ensure_consumer creates EventConsumer on first call."""
        from services.retrieval.app.retrieval import RetrievalService

        mock_consumer = Mock()
        sys.modules["retrieval_rabbitmq"].EventConsumer.return_value = mock_consumer

        service = RetrievalService(rabbitmq_host="rabbitmq")

        result = service._ensure_consumer()

        assert result == mock_consumer
        assert service.consumer == mock_consumer
        sys.modules["retrieval_rabbitmq"].EventConsumer.assert_called_once_with(
            rabbitmq_host="rabbitmq"
        )

    def test_ensure_consumer_returns_existing_consumer(self):
        """Test _ensure_consumer returns existing consumer without creating new one."""
        from services.retrieval.app.retrieval import RetrievalService

        existing_consumer = Mock()
        service = RetrievalService(rabbitmq_host="rabbitmq")
        service.consumer = existing_consumer

        result = service._ensure_consumer()

        assert result == existing_consumer
        sys.modules["retrieval_rabbitmq"].EventConsumer.assert_not_called()

    def test_ensure_retriever_creates_new_retriever(self):
        """Test _ensure_retriever creates retriever on first call."""
        from services.retrieval.app.retrieval import RetrievalService

        mock_retriever = Mock()
        sys.modules["retriever"].get_retriever.return_value = mock_retriever

        service = RetrievalService(rabbitmq_host="rabbitmq")

        result = service._ensure_retriever()

        assert result == mock_retriever
        assert service.retriever == mock_retriever
        sys.modules["retriever"].get_retriever.assert_called_once()

    def test_ensure_retriever_returns_existing_retriever(self):
        """Test _ensure_retriever returns existing retriever."""
        from services.retrieval.app.retrieval import RetrievalService

        existing_retriever = Mock()
        service = RetrievalService(rabbitmq_host="rabbitmq")
        service.retriever = existing_retriever

        result = service._ensure_retriever()

        assert result == existing_retriever
        sys.modules["retriever"].get_retriever.assert_not_called()

    def test_start_subscribes_to_events(self):
        """Test start() subscribes to required RabbitMQ events."""
        from services.retrieval.app.retrieval import RetrievalService

        mock_consumer = Mock()
        sys.modules["retrieval_rabbitmq"].EventConsumer.return_value = mock_consumer

        service = RetrievalService(rabbitmq_host="rabbitmq")
        service.start()

        # Verify subscriptions
        assert mock_consumer.subscribe.call_count == 2

        calls = mock_consumer.subscribe.call_args_list
        events = [call[0][0] for call in calls]

        assert "QueryReceived" in events
        assert "chunks.indexed" in events

    def test_start_begins_consuming(self):
        """Test start() begins consuming RabbitMQ messages."""
        from services.retrieval.app.retrieval import RetrievalService

        mock_consumer = Mock()
        sys.modules["retrieval_rabbitmq"].EventConsumer.return_value = mock_consumer

        service = RetrievalService(rabbitmq_host="rabbitmq")
        service.start()

        mock_consumer.start_consuming.assert_called_once()

    def test_handle_chunks_indexed_success(self):
        """Test handle_chunks_indexed processes valid event."""
        from services.retrieval.app.retrieval import RetrievalService

        mock_retriever = Mock()
        sys.modules["retriever"].get_retriever.return_value = mock_retriever

        service = RetrievalService(rabbitmq_host="rabbitmq")

        # Prepare mock RabbitMQ message
        ch = Mock()
        method = Mock(delivery_tag="test-tag")
        properties = Mock(correlation_id="corr-123")

        event_data = {
            "eventType": "ChunksIndexed",
            "payload": {"documentId": "doc-456", "chunkIndex": 0, "totalChunks": 42},
        }
        body = json.dumps(event_data).encode()

        service.handle_chunks_indexed(ch, method, properties, body)

        # Verify message acknowledged
        ch.basic_ack.assert_called_once_with(delivery_tag="test-tag")

    def test_handle_chunks_indexed_invalid_json(self):
        """Test handle_chunks_indexed handles malformed JSON."""
        from services.retrieval.app.retrieval import RetrievalService

        service = RetrievalService(rabbitmq_host="rabbitmq")

        ch = Mock()
        method = Mock(delivery_tag="test-tag")
        properties = Mock(correlation_id="corr-123")
        body = b"invalid json{{{{"

        service.handle_chunks_indexed(ch, method, properties, body)

        # Should still acknowledge message
        ch.basic_ack.assert_called_once_with(delivery_tag="test-tag")

    def test_handle_chunks_indexed_missing_correlation_id(self):
        """Test handle_chunks_indexed handles missing correlation_id."""
        from services.retrieval.app.retrieval import RetrievalService

        service = RetrievalService(rabbitmq_host="rabbitmq")

        ch = Mock()
        method = Mock(delivery_tag="test-tag")
        properties = Mock(correlation_id=None)
        body = json.dumps(
            {"eventType": "ChunksIndexed", "payload": {"documentId": "doc1"}}
        ).encode()

        service.handle_chunks_indexed(ch, method, properties, body)

        ch.basic_ack.assert_called_once()

    def test_handle_query_received_success(self):
        """Test handle_query_received retrieves and publishes results."""
        from services.retrieval.app.retrieval import RetrievalService

        mock_retriever = Mock()
        mock_retriever.search.return_value = [
            {"content": "chunk1", "relevanceScore": 0.95},
            {"content": "chunk2", "relevanceScore": 0.87},
        ]
        sys.modules["retriever"].get_retriever.return_value = mock_retriever

        service = RetrievalService(rabbitmq_host="rabbitmq")

        ch = Mock()
        method = Mock(delivery_tag="test-tag")
        properties = Mock(correlation_id="query-123")

        query_event = {
            "eventType": "QueryReceived",
            "payload": {"queryId": "q-456", "queryText": "What is MARP?"},
        }
        body = json.dumps(query_event).encode()

        service.handle_query_received(ch, method, properties, body)

        # Verify search called
        mock_retriever.search.assert_called_once_with("What is MARP?", top_k=5)

        # Verify message acknowledged
        ch.basic_ack.assert_called_once_with(delivery_tag="test-tag")

        # Verify TWO events published (RetrievalCompleted + ChunksRetrieved)
        assert sys.modules["retrieval_events"].publish_event.call_count == 2
        # First call: RetrievalCompleted
        assert (
            sys.modules["retrieval_events"].publish_event.call_args_list[0][0][0]
            == "RetrievalCompleted"
        )
        # Second call: ChunksRetrieved
        assert (
            "CHUNKS_RETRIEVED"
            in str(
                sys.modules["retrieval_events"].publish_event.call_args_list[1][0][0]
            )
            or sys.modules["retrieval_events"].publish_event.call_args_list[1][0][0]
            == "ChunksRetrieved"
        )

    def test_handle_query_received_empty_results(self):
        """Test handle_query_received with no results found."""
        from services.retrieval.app.retrieval import RetrievalService

        mock_retriever = Mock()
        mock_retriever.search.return_value = []
        sys.modules["retriever"].get_retriever.return_value = mock_retriever

        service = RetrievalService(rabbitmq_host="rabbitmq")

        ch = Mock()
        method = Mock(delivery_tag="test-tag")
        properties = Mock(correlation_id="query-456")

        body = json.dumps(
            {
                "eventType": "QueryReceived",
                "payload": {"queryId": "q-789", "queryText": "unknown topic"},
            }
        ).encode()

        service.handle_query_received(ch, method, properties, body)

        # Should still publish event with empty results
        ch.basic_ack.assert_called_once()

    def test_handle_query_received_default_top_k(self):
        """Test handle_query_received uses default top_k if not specified."""
        from services.retrieval.app.retrieval import RetrievalService

        mock_retriever = Mock()
        mock_retriever.search.return_value = []
        sys.modules["retriever"].get_retriever.return_value = mock_retriever

        service = RetrievalService(rabbitmq_host="rabbitmq")

        ch = Mock()
        method = Mock(delivery_tag="test-tag")
        properties = Mock(correlation_id="query-789")

        # Event without top_k
        body = json.dumps(
            {
                "eventType": "QueryReceived",
                "payload": {"queryId": "q-123", "queryText": "test"},
            }
        ).encode()

        service.handle_query_received(ch, method, properties, body)

        # Should use default top_k=5
        mock_retriever.search.assert_called_once_with("test", top_k=5)

    def test_handle_query_received_invalid_json(self):
        """Test handle_query_received handles malformed JSON."""
        from services.retrieval.app.retrieval import RetrievalService

        service = RetrievalService(rabbitmq_host="rabbitmq")

        ch = Mock()
        method = Mock(delivery_tag="test-tag")
        properties = Mock(correlation_id="query-bad")
        body = b"not json"

        service.handle_query_received(ch, method, properties, body)

        # Should ACK invalid JSON (not nack) to remove from queue
        ch.basic_ack.assert_called_once()

    def test_handle_query_received_retrieval_error(self):
        """Test handle_query_received handles retrieval exceptions."""
        from services.retrieval.app.retrieval import RetrievalService

        mock_retriever = Mock()
        mock_retriever.search.side_effect = Exception("Database connection failed")
        sys.modules["retriever"].get_retriever.return_value = mock_retriever

        service = RetrievalService(rabbitmq_host="rabbitmq")

        ch = Mock()
        method = Mock(delivery_tag="test-tag")
        properties = Mock(correlation_id="query-error")
        body = json.dumps(
            {
                "eventType": "QueryReceived",
                "payload": {"queryId": "q-err", "queryText": "test"},
            }
        ).encode()

        service.handle_query_received(ch, method, properties, body)

        # Should nack message
        ch.basic_nack.assert_called_once()

    def test_handle_query_received_missing_query_field(self):
        """Test handle_query_received handles missing query field."""
        from services.retrieval.app.retrieval import RetrievalService

        service = RetrievalService(rabbitmq_host="rabbitmq")

        ch = Mock()
        method = Mock(delivery_tag="test-tag")
        properties = Mock(correlation_id="query-123")

        # Event missing 'queryText' field
        body = json.dumps(
            {"eventType": "QueryReceived", "payload": {"queryId": "q-123"}}
        ).encode()

        service.handle_query_received(ch, method, properties, body)

        ch.basic_ack.assert_called_once()
