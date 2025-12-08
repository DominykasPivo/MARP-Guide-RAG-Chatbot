"""
Unit tests for EventConsumer (RabbitMQ consumer with exponential backoff).

Target: services/retrieval/app/retrieval_rabbitmq.py
Coverage: 87 statements at 0%
"""

import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest


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
