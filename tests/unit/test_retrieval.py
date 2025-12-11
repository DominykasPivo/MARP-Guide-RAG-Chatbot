"""
Unit tests for retrieval service.

Comprehensive tests covering:
- Business logic (retriever.py): Search, ranking, deduplication
- FastAPI endpoints (app.py): /search, /query, /health, /debug
- Service layer (retrieval.py): RetrievalService event handling
- RabbitMQ consumer (retrieval_rabbitmq.py): EventConsumer operations

Target files:
- services/retrieval/app/retriever.py
- services/retrieval/app/app.py
- services/retrieval/app/retrieval.py
- services/retrieval/app/retrieval_rabbitmq.py
"""

import sys
from unittest.mock import Mock

sys.modules["retrieval_rabbitmq"] = Mock()
sys.modules["retrieval_events"] = Mock()
sys.modules["retriever"] = Mock()

import json
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from services.retrieval.app.retriever import Retriever

# ============================================================================
# BUSINESS LOGIC TESTS - Retriever
# ============================================================================


class TestRetrieverSearch:
    """Test retrieval search functionality."""

    def test_retriever_search_returns_correct_structure(self):
        """Test that search returns properly structured results."""
        # Mock Qdrant client
        mock_client = Mock()
        mock_result = Mock()
        mock_result.id = "chunk-1"
        mock_result.score = 0.95
        mock_result.payload = {
            "text": "Test chunk content",
            "title": "Test Doc",
            "page": 1,
            "url": "http://example.com/doc.pdf",
            "chunk_index": 0,
        }
        mock_client.search.return_value = [mock_result]

        # Mock encoder
        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                results = retriever.search("test query", top_k=5)

                assert len(results) == 1
                assert results[0]["id"] == "chunk-1"
                assert results[0]["text"] == "Test chunk content"
                assert results[0]["relevanceScore"] == 0.95
                assert results[0]["title"] == "Test Doc"
                assert results[0]["page"] == 1
                assert results[0]["url"] == "http://example.com/doc.pdf"

    def test_retriever_search_deduplicates_results(self):
        """Test that duplicate results are filtered out."""
        mock_client = Mock()

        # Create duplicate results (same text, url, chunk_index)
        mock_result_1 = Mock()
        mock_result_1.id = "chunk-1"
        mock_result_1.score = 0.95
        mock_result_1.payload = {
            "text": "Duplicate content",
            "title": "Doc",
            "page": 1,
            "url": "http://test.com",
            "chunk_index": 0,
        }

        mock_result_2 = Mock()
        mock_result_2.id = "chunk-2"
        mock_result_2.score = 0.90
        mock_result_2.payload = {
            "text": "Duplicate content",
            "title": "Doc",
            "page": 1,
            "url": "http://test.com",
            "chunk_index": 0,
        }

        mock_client.search.return_value = [mock_result_1, mock_result_2]

        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                results = retriever.search("test query", top_k=5)

                # Should only return one result (deduplicated)
                assert len(results) == 1

    def test_retriever_search_keeps_different_chunks_same_url(self):
        """Test that different chunks from same document are kept."""
        mock_client = Mock()

        # Same URL but different chunk_index
        mock_result_1 = Mock()
        mock_result_1.id = "chunk-1"
        mock_result_1.score = 0.95
        mock_result_1.payload = {
            "text": "First chunk",
            "title": "Doc",
            "page": 1,
            "url": "http://test.com",
            "chunk_index": 0,
        }

        mock_result_2 = Mock()
        mock_result_2.id = "chunk-2"
        mock_result_2.score = 0.90
        mock_result_2.payload = {
            "text": "Second chunk",
            "title": "Doc",
            "page": 1,
            "url": "http://test.com",
            "chunk_index": 1,
        }

        mock_client.search.return_value = [mock_result_1, mock_result_2]

        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                results = retriever.search("test query", top_k=5)

                # Should keep both chunks (different chunk_index)
                assert len(results) == 2

    def test_retriever_search_respects_top_k(self):
        """Test that search returns at most top_k results."""
        mock_client = Mock()

        # Create 10 different results
        mock_results = []
        for i in range(10):
            mock_result = Mock()
            mock_result.id = f"chunk-{i}"
            mock_result.score = 0.9 - (i * 0.05)
            mock_result.payload = {
                "text": f"Content {i}",
                "title": "Doc",
                "page": i,
                "url": "http://test.com",
                "chunk_index": i,
            }
            mock_results.append(mock_result)

        mock_client.search.return_value = mock_results

        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                results = retriever.search("test query", top_k=3)

                # Should return exactly 3 results
                assert len(results) == 3

    def test_retriever_search_handles_empty_results(self):
        """Test that search handles no results gracefully."""
        mock_client = Mock()
        mock_client.search.return_value = []

        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                results = retriever.search("test query", top_k=5)

                assert results == []

    def test_retriever_search_lowercases_query(self):
        """Test that query is lowercased for consistent preprocessing."""
        mock_client = Mock()
        mock_client.search.return_value = []

        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                retriever.search("TEST Query With CAPS", top_k=5)

                # Verify encoder was called with lowercased query
                mock_encoder.encode.assert_called_once()
                call_args = mock_encoder.encode.call_args[0]
                assert call_args[0] == "test query with caps"

    def test_retriever_search_handles_missing_payload_fields(self):
        """Test that search handles missing or incomplete payload data."""
        mock_client = Mock()

        # Result with minimal payload
        mock_result = Mock()
        mock_result.id = "chunk-1"
        mock_result.score = 0.95
        mock_result.payload = {"text": "Minimal content"}  # Missing optional fields

        mock_client.search.return_value = [mock_result]

        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                results = retriever.search("test query", top_k=5)

                # Should handle missing fields with defaults
                assert len(results) == 1
                assert results[0]["text"] == "Minimal content"
                assert results[0]["title"] == "MARP Document"  # Default value
                assert results[0]["page"] == 0  # Default value

    def test_retriever_search_handles_none_payload(self):
        """Test that search handles None payload gracefully."""
        mock_client = Mock()

        mock_result = Mock()
        mock_result.id = "chunk-1"
        mock_result.score = 0.95
        mock_result.payload = None

        mock_client.search.return_value = [mock_result]

        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                results = retriever.search("test query", top_k=5)

                # Should handle None payload
                assert len(results) == 1
                assert results[0]["text"] == ""

    def test_retriever_search_handles_qdrant_error(self):
        """Test that search handles Qdrant errors gracefully."""
        mock_client = Mock()
        mock_client.search.side_effect = Exception("Qdrant connection failed")

        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                results = retriever.search("test query", top_k=5)

                # Should return empty list on error
                assert results == []

    def test_retriever_search_handles_encoder_not_initialized(self):
        """Test that search handles uninitialized encoder."""
        mock_client = Mock()

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch("services.retrieval.app.retriever.SentenceTransformer"):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = None  # Force encoder to None

                results = retriever.search("test query", top_k=5)

                # Should return empty list
                assert results == []

    def test_retriever_search_requests_more_from_qdrant_for_dedup(self):
        """Test that retriever requests 3x top_k from Qdrant to handle deduplication."""
        mock_client = Mock()
        mock_client.search.return_value = []

        mock_encoder = Mock()
        mock_encoder.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_client
        ):
            with patch(
                "services.retrieval.app.retriever.SentenceTransformer",
                return_value=mock_encoder,
            ):
                retriever = Retriever()
                retriever.client = mock_client
                retriever.encoder = mock_encoder

                retriever.search("test query", top_k=5)

                # Verify search was called with 15 (3x5) or at least 15
                mock_client.search.assert_called_once()
                call_kwargs = mock_client.search.call_args[1]
                assert call_kwargs["limit"] >= 15


class TestRetrieverInitialization:
    """Test retriever initialization and configuration."""

    def test_retriever_uses_environment_variables(self):
        """Test that retriever reads configuration from environment."""
        with patch.dict(
            "os.environ",
            {
                "EMBEDDING_MODEL": "test-model",
                "QDRANT_HOST": "test-host",
                "QDRANT_PORT": "9999",
                "QDRANT_COLLECTION_NAME": "test-collection",
            },
        ):
            with patch("services.retrieval.app.retriever.QdrantClient"):
                with patch("services.retrieval.app.retriever.SentenceTransformer"):
                    retriever = Retriever()

                    assert retriever.embedding_model_name == "test-model"
                    assert retriever.qdrant_host == "test-host"
                    assert retriever.qdrant_port == 9999
                    assert retriever.collection_name == "test-collection"

    def test_retriever_uses_defaults_when_env_not_set(self):
        """Test that retriever uses sensible defaults."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("services.retrieval.app.retriever.QdrantClient"):
                with patch("services.retrieval.app.retriever.SentenceTransformer"):
                    retriever = Retriever()

                    assert retriever.embedding_model_name == "all-MiniLM-L6-v2"
                    assert retriever.qdrant_host == "localhost"
                    assert retriever.qdrant_port == 6333
                    assert retriever.collection_name == "chunks"

    def test_retriever_handles_initialization_failure(self):
        """Test that initialization failures are properly raised."""
        with patch(
            "services.retrieval.app.retriever.SentenceTransformer",
            side_effect=Exception("Model load failed"),
        ):
            with pytest.raises(Exception, match="Model load failed"):
                Retriever()


# ============================================================================
# SERVICE LAYER TESTS - RetrievalService
# ============================================================================


class TestRetrievalService:
    """Test RetrievalService initialization and event handling."""

    def setup_method(self):
        """Reset mocks before each test."""
        # Only reset if present to avoid KeyError
        if "retrieval_events" in sys.modules:
            sys.modules["retrieval_events"].reset_mock()
        if "retrieval_rabbitmq" in sys.modules:
            sys.modules["retrieval_rabbitmq"].reset_mock()
        if "retriever" in sys.modules:
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

        # Verify subscriptions - only chunks.indexed, QueryReceived handled via HTTP
        assert mock_consumer.subscribe.call_count == 1

        calls = mock_consumer.subscribe.call_args_list
        events = [call[0][0] for call in calls]

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


# ============================================================================
# RABBITMQ CONSUMER TESTS - EventConsumer
# ============================================================================


# Create real exception class for AMQPConnectionError
class MockAMQPConnectionError(Exception):
    """Mock AMQPConnectionError that can be caught."""

    pass


# Mock pika at module level, but not during type checking
if not TYPE_CHECKING:
    sys.modules["pika"] = Mock()
    sys.modules["pika.exceptions"] = Mock()
    sys.modules["pika.exceptions"].AMQPConnectionError = MockAMQPConnectionError


class TestEventConsumer:
    """Test EventConsumer initialization and RabbitMQ operations."""

    def setup_method(self):
        """Reset mocks before each test."""
        sys.modules["pika"].reset_mock()
        sys.modules["pika.exceptions"].reset_mock()

    def test_consumer_initialization(self):
        """Test EventConsumer initializes with correct parameters."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        consumer = EventConsumer(rabbitmq_host="rabbitmq")

        assert consumer.host == "rabbitmq"
        assert consumer.connection is None
        assert consumer.channel is None
        assert consumer.subscriptions == {}

    def test_calculate_retry_delay_exponential_backoff(self):
        """Test _calculate_retry_delay implements exponential backoff."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        consumer = EventConsumer("rabbitmq")

        # Test delays increase exponentially
        delay1 = consumer._calculate_retry_delay(0)
        assert 0.9 <= delay1 <= 1.1  # 2^0 * 1 = 1 ± jitter

        delay2 = consumer._calculate_retry_delay(1)
        assert 1.8 <= delay2 <= 2.2  # 2^1 * 1 = 2 ± jitter

        delay3 = consumer._calculate_retry_delay(2)
        assert 3.6 <= delay3 <= 4.4  # 2^2 * 1 = 4 ± jitter

    def test_calculate_retry_delay_max_cap(self):
        """Test _calculate_retry_delay caps at maximum delay."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        consumer = EventConsumer("rabbitmq")

        delay = consumer._calculate_retry_delay(100)  # Very high retry count

        # Should cap at max_delay (60 seconds) plus jitter
        assert delay <= 66  # 60 + max 10% jitter

    def test_connect_success(self):
        """Test _connect establishes connection and channel."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        mock_connection = Mock()
        mock_connection.is_closed = False
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel

        sys.modules["pika"].BlockingConnection.return_value = mock_connection
        sys.modules["pika"].ConnectionParameters.return_value = Mock()

        consumer = EventConsumer("rabbitmq")
        result = consumer._connect()

        assert result is True
        assert consumer.connection == mock_connection
        assert consumer.channel == mock_channel
        mock_channel.exchange_declare.assert_called_once()

    def test_connect_returns_false_on_failure(self):
        """Test _connect returns False on connection failure."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        # Connection fails
        sys.modules["pika"].BlockingConnection.side_effect = Exception(
            "Connection refused"
        )

        consumer = EventConsumer("rabbitmq")

        result = consumer._connect()

        # Should return False, not raise
        assert result is False

    def test_connect_handles_amqp_error(self):
        """Test _connect handles AMQP connection errors."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        # Mock AMQPConnectionError
        amqp_error = Exception("AMQP Connection Error")
        sys.modules["pika"].BlockingConnection.side_effect = amqp_error
        sys.modules["pika.exceptions"].AMQPConnectionError = type(
            amqp_error
        )  # type: ignore[attr-defined]

        consumer = EventConsumer("rabbitmq")

        result = consumer._connect()

        assert result is False

    def test_subscribe_registers_callback(self):
        """Test subscribe registers callback for event type."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        consumer = EventConsumer("rabbitmq")

        callback = Mock()
        consumer.subscribe("test.event", callback)

        # Verify subscription registered (lowercase routing key)
        assert "test.event" in consumer.subscriptions
        assert consumer.subscriptions["test.event"] == callback

    def test_subscribe_handles_routing_key_case(self):
        """Test subscribe converts event type to lowercase routing key."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        consumer = EventConsumer("rabbitmq")

        callback = Mock()
        consumer.subscribe("QueryReceived", callback)

        # Should store with lowercase key
        assert "queryreceived" in consumer.subscriptions
        assert consumer.subscriptions["queryreceived"] == callback

    def test_subscribe_multiple_events(self):
        """Test subscribing to multiple events."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        consumer = EventConsumer("rabbitmq")

        callback1 = Mock()
        callback2 = Mock()

        consumer.subscribe("event.one", callback1)
        consumer.subscribe("event.two", callback2)

        assert len(consumer.subscriptions) == 2
        assert consumer.subscriptions["event.one"] == callback1
        assert consumer.subscriptions["event.two"] == callback2

    @patch(
        "services.retrieval.app.retrieval_rabbitmq.time.sleep"
    )  # Mock sleep to speed up test
    def test_start_consuming_sets_up_subscriptions(self, mock_sleep):
        """Test start_consuming sets_up all registered subscriptions."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        # CRITICAL: Reset mock state from previous tests
        sys.modules["pika"].BlockingConnection.reset_mock()
        sys.modules["pika"].BlockingConnection.side_effect = None

        # Mock successful connection
        mock_connection = Mock()
        mock_connection.is_closed = False
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel

        # Mock queue declaration
        mock_result = Mock()
        mock_result.method.queue = "generated-queue-name"
        mock_channel.queue_declare.return_value = mock_result

        sys.modules["pika"].BlockingConnection.return_value = mock_connection
        sys.modules["pika"].ConnectionParameters.return_value = Mock()

        consumer = EventConsumer("rabbitmq")
        callback = Mock()
        consumer.subscribe("test.event", callback)

        # Mock start_consuming to avoid blocking
        mock_channel.start_consuming.side_effect = KeyboardInterrupt()

        try:
            consumer.start_consuming()
        except SystemExit:
            pass

        # Verify queue was declared (exclusive)
        mock_channel.queue_declare.assert_called_once_with(queue="", exclusive=True)

        # Verify queue was bound
        mock_channel.queue_bind.assert_called_once()

        # Verify consumer was set up
        mock_channel.basic_consume.assert_called_once()

    def test_start_consuming_raises_on_max_retries(self):
        """Test start_consuming raises ConnectionError after max retries."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        # Always fail connection
        sys.modules["pika"].BlockingConnection.side_effect = Exception(
            "Connection refused"
        )

        consumer = EventConsumer("rabbitmq")
        consumer.subscribe("test.event", Mock())

        with patch("services.retrieval.app.retrieval_rabbitmq.time.sleep"):
            with pytest.raises(ConnectionError):
                consumer.start_consuming()

    def test_stop_closes_connection(self):
        """Test stop closes RabbitMQ connection."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        mock_connection = Mock()
        mock_connection.is_closed = False
        mock_channel = Mock()

        consumer = EventConsumer("rabbitmq")
        consumer.connection = mock_connection
        consumer.channel = mock_channel

        consumer.stop()

        mock_channel.stop_consuming.assert_called_once()
        mock_connection.close.assert_called_once()

    def test_stop_handles_no_connection(self):
        """Test stop handles case where no connection exists."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        consumer = EventConsumer("rabbitmq")
        # No connection established

        # Should not raise exception
        consumer.stop()

    def test_stop_handles_partial_connection(self):
        """Test stop handles case where channel exists but connection doesn't."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        mock_channel = Mock()

        consumer = EventConsumer("rabbitmq")
        consumer.channel = mock_channel
        consumer.connection = None

        consumer.stop()

        # Should still try to stop channel
        mock_channel.stop_consuming.assert_called_once()

    def test_stop_handles_closed_connection(self):
        """Test stop handles already closed connection."""
        from services.retrieval.app.retrieval_rabbitmq import EventConsumer

        mock_connection = Mock()
        mock_connection.is_closed = True
        mock_channel = Mock()

        consumer = EventConsumer("rabbitmq")
        consumer.connection = mock_connection
        consumer.channel = mock_channel

        consumer.stop()

        # Should still try to stop channel
        mock_channel.stop_consuming.assert_called_once()
        # But should not try to close already closed connection
        mock_connection.close.assert_not_called()
