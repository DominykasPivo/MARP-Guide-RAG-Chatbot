"""
Unit tests for RabbitMQ connection and retry logic.

Uses fakes/mocks/fixtures for isolated unit testing following the pattern from test_ingestion_flow.py
"""

import json
from unittest.mock import MagicMock

import pytest


# --- Fake RabbitMQ for Testing ---


class FakeRabbitMQPublisher:
    """Fake RabbitMQ publisher for testing without actual RabbitMQ."""

    def __init__(self, host: str = "localhost", should_fail: bool = False):
        self.host = host
        self.connection = None
        self.channel = None
        self.published_events = []
        self.connection_attempts = 0
        self.should_fail = should_fail
        self.is_connected = False

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = min(1 * (2**attempt), 60)
        return delay

    def _connect(self) -> bool:
        """Fake connection method."""
        self.connection_attempts += 1

        if self.should_fail:
            return False

        self.is_connected = True
        self.connection = MagicMock()
        self.channel = MagicMock()
        return True

    def publish_event(
        self, event_type: str, event_data: dict, correlation_id: str = None
    ) -> bool:
        """Fake publish event method."""
        if not self.is_connected and not self._connect():
            return False

        self.published_events.append(
            {
                "event_type": event_type,
                "data": event_data,
                "correlation_id": correlation_id,
            }
        )
        return True

    def close(self):
        """Fake close method."""
        self.is_connected = False
        self.connection = None
        self.channel = None


# --- Pytest Fixtures ---


@pytest.fixture
def fake_publisher():
    """Provide a fake RabbitMQ publisher."""
    return FakeRabbitMQPublisher()


@pytest.fixture
def fake_failing_publisher():
    """Provide a fake publisher that always fails."""
    return FakeRabbitMQPublisher(should_fail=True)


# --- Unit Tests ---


class TestRabbitMQInitialization:
    """Test RabbitMQ publisher initialization."""

    def test_init_with_default_host(self, fake_publisher):
        """Test initialization with default localhost."""
        assert fake_publisher.host == "localhost"
        assert fake_publisher.connection_attempts == 0
        assert not fake_publisher.is_connected

    def test_init_with_custom_host(self):
        """Test initialization with custom host."""
        publisher = FakeRabbitMQPublisher(host="rabbitmq.example.com")
        assert publisher.host == "rabbitmq.example.com"

    def test_retry_delay_calculation(self, fake_publisher):
        """Test exponential backoff calculation."""
        # Test exponential backoff: 1, 2, 4, 8, 16
        assert fake_publisher._calculate_retry_delay(0) == 1
        assert fake_publisher._calculate_retry_delay(1) == 2
        assert fake_publisher._calculate_retry_delay(2) == 4
        assert fake_publisher._calculate_retry_delay(3) == 8
        assert fake_publisher._calculate_retry_delay(4) == 16

    def test_max_retry_delay(self, fake_publisher):
        """Test maximum retry delay cap at 60 seconds."""
        assert fake_publisher._calculate_retry_delay(10) == 60
        assert fake_publisher._calculate_retry_delay(100) == 60


class TestRabbitMQConnection:
    """Test RabbitMQ connection logic."""

    def test_successful_connection(self, fake_publisher):
        """Test successful connection establishment."""
        result = fake_publisher._connect()

        assert result is True
        assert fake_publisher.is_connected
        assert fake_publisher.connection_attempts == 1
        assert fake_publisher.connection is not None
        assert fake_publisher.channel is not None

    def test_connection_failure(self, fake_failing_publisher):
        """Test connection failure."""
        result = fake_failing_publisher._connect()

        assert result is False
        assert not fake_failing_publisher.is_connected
        assert fake_failing_publisher.connection_attempts == 1

    def test_multiple_connection_attempts(self, fake_failing_publisher):
        """Test multiple connection attempts."""
        # Try connecting 3 times
        for _ in range(3):
            fake_failing_publisher._connect()

        assert fake_failing_publisher.connection_attempts == 3
        assert not fake_failing_publisher.is_connected


class TestEventPublishing:
    """Test event publishing functionality."""

    def test_publish_event_success(self, fake_publisher):
        """Test successful event publishing."""
        event_data = {
            "eventType": "DocumentDiscovered",
            "documentId": "doc-123",
            "url": "https://example.com/doc.pdf",
        }

        result = fake_publisher.publish_event("DocumentDiscovered", event_data)

        assert result is True
        assert len(fake_publisher.published_events) == 1
        assert (
            fake_publisher.published_events[0]["event_type"] == "DocumentDiscovered"
        )
        assert fake_publisher.published_events[0]["data"] == event_data

    def test_publish_event_with_correlation_id(self, fake_publisher):
        """Test event publishing with correlation ID."""
        event_data = {"data": "test"}
        correlation_id = "corr-456"

        result = fake_publisher.publish_event(
            "TestEvent", event_data, correlation_id=correlation_id
        )

        assert result is True
        assert len(fake_publisher.published_events) == 1
        assert fake_publisher.published_events[0]["correlation_id"] == correlation_id

    def test_publish_event_auto_connects(self):
        """Test that publishing automatically connects."""
        publisher = FakeRabbitMQPublisher()
        event_data = {"test": "data"}

        # Not connected yet
        assert not publisher.is_connected

        # Publishing should auto-connect
        result = publisher.publish_event("TestEvent", event_data)

        assert result is True
        assert publisher.is_connected
        assert len(publisher.published_events) == 1

    def test_publish_event_fails_when_no_connection(self, fake_failing_publisher):
        """Test publishing fails when connection cannot be established."""
        event_data = {"test": "data"}

        result = fake_failing_publisher.publish_event("TestEvent", event_data)

        assert result is False
        assert len(fake_failing_publisher.published_events) == 0

    def test_multiple_event_publishing(self, fake_publisher):
        """Test publishing multiple events."""
        events = [
            {"eventType": "Event1", "data": "test1"},
            {"eventType": "Event2", "data": "test2"},
            {"eventType": "Event3", "data": "test3"},
        ]

        for event in events:
            result = fake_publisher.publish_event(event["eventType"], event)
            assert result is True

        assert len(fake_publisher.published_events) == 3


class TestConnectionManagement:
    """Test connection management."""

    def test_close_connection(self, fake_publisher):
        """Test closing connection."""
        # Connect first
        fake_publisher._connect()
        assert fake_publisher.is_connected

        # Close connection
        fake_publisher.close()

        assert not fake_publisher.is_connected
        assert fake_publisher.connection is None
        assert fake_publisher.channel is None

    def test_reconnection_after_close(self, fake_publisher):
        """Test reconnection after closing."""
        # Connect, close, reconnect
        fake_publisher._connect()
        fake_publisher.close()
        result = fake_publisher._connect()

        assert result is True
        assert fake_publisher.is_connected
        assert fake_publisher.connection_attempts == 2

    def test_close_when_not_connected(self, fake_publisher):
        """Test closing when not connected doesn't cause errors."""
        # Should not raise any exceptions
        fake_publisher.close()

        assert not fake_publisher.is_connected
        assert fake_publisher.connection is None


class TestEventSerialization:
    """Test event data serialization."""

    def test_event_data_json_serialization(self, fake_publisher):
        """Test that event data can be JSON serialized."""
        event_data = {
            "documentId": "doc-123",
            "url": "https://example.com/doc.pdf",
            "timestamp": "2024-11-27T12:00:00",
        }

        fake_publisher.publish_event("DocumentDiscovered", event_data)

        # Verify data can be JSON serialized
        published = fake_publisher.published_events[0]
        json_str = json.dumps(published["data"])
        assert json_str is not None
        assert "doc-123" in json_str

    def test_event_with_complex_nested_data(self, fake_publisher):
        """Test event with complex nested data structures."""
        event_data = {
            "documentId": "doc-456",
            "metadata": {
                "author": "Test Author",
                "tags": ["tag1", "tag2"],
                "nested": {"key": "value", "list": [1, 2, 3]},
            },
        }

        fake_publisher.publish_event("DocumentProcessed", event_data)

        published = fake_publisher.published_events[0]
        assert published["data"]["metadata"]["author"] == "Test Author"
        assert len(published["data"]["metadata"]["tags"]) == 2
        assert published["data"]["metadata"]["nested"]["key"] == "value"

    def test_event_serialization_with_none_correlation_id(self, fake_publisher):
        """Test event serialization with None correlation ID."""
        event_data = {"test": "data"}

        fake_publisher.publish_event("TestEvent", event_data, correlation_id=None)

        published = fake_publisher.published_events[0]
        json_str = json.dumps(
            {
                "event_type": published["event_type"],
                "data": published["data"],
                "correlation_id": published["correlation_id"],
            }
        )
        assert json_str is not None


class TestRabbitMQEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_event_data(self, fake_publisher):
        """Test publishing event with empty data."""
        result = fake_publisher.publish_event("EmptyEvent", {})

        assert result is True
        assert len(fake_publisher.published_events) == 1
        assert fake_publisher.published_events[0]["data"] == {}

    def test_unicode_in_event_data(self, fake_publisher):
        """Test event data with unicode characters."""
        event_data = {
            "text": "Hello 世界 🌍",
            "author": "José García",
        }

        result = fake_publisher.publish_event("UnicodeEvent", event_data)

        assert result is True
        published = fake_publisher.published_events[0]
        assert published["data"]["text"] == "Hello 世界 🌍"
        assert published["data"]["author"] == "José García"

        # Verify JSON serialization works (JSON escapes unicode by default)
        json_str = json.dumps(published["data"])
        assert "\\u4e16\\u754c" in json_str or "世界" in json_str  # Accept both escaped and unescaped

    def test_large_event_data(self, fake_publisher):
        """Test publishing large event data."""
        # Create event with large payload
        large_list = [{"id": i, "data": f"item-{i}" * 100} for i in range(100)]
        event_data = {"items": large_list}

        result = fake_publisher.publish_event("LargeEvent", event_data)

        assert result is True
        assert len(fake_publisher.published_events) == 1
        assert len(fake_publisher.published_events[0]["data"]["items"]) == 100
