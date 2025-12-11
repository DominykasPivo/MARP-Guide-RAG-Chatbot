"""RabbitMQ event publisher for ingestion service with enhanced retry logic."""

import json
import logging
import os
import random
import time
from typing import Optional

import pika
from events import DocumentDiscovered, EventTypes
from pika.exceptions import AMQPChannelError, AMQPConnectionError, AMQPError

# Configure logging
logger = logging.getLogger("ingestion.rabbitmq")

# Constants from environment
MAX_RETRIES = int(os.getenv("RABBITMQ_MAX_RETRIES", "5"))
INITIAL_RETRY_DELAY = int(os.getenv("RABBITMQ_INITIAL_RETRY_DELAY", "1"))
MAX_RETRY_DELAY = int(os.getenv("RABBITMQ_MAX_RETRY_DELAY", "30"))
JITTER_RANGE = 0.1
CONNECTION_TIMEOUT = int(os.getenv("RABBITMQ_CONNECTION_TIMEOUT", "30"))
EXCHANGE_NAME = "document_events"


class EventPublisher:
    """Handles publishing events to RabbitMQ with automatic reconnection and retries."""

    def __init__(self, host: str = "localhost"):
        """Initialize the event publisher.

        Args:
            host: RabbitMQ host address
        """
        self.host = host
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        # Don't raise if initial connection fails
        try:
            self._connect()
        except AMQPError as e:
            logger.error(f"Failed to establish initial connection: {str(e)}")

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter.

        Args:
            attempt: The current retry attempt number (0-based)

        Returns:
            float: The delay to wait before the next retry in seconds
        """
        # Calculate exponential backoff
        delay: float = min(INITIAL_RETRY_DELAY * (2**attempt), MAX_RETRY_DELAY)

        # Add jitter
        jitter = delay * JITTER_RANGE
        delay += random.uniform(-jitter, jitter)  # nosec B311
        return max(0.0, delay)  # Ensure non-negative delay

    def _connect(self) -> bool:
        """Establish connection to RabbitMQ and set up exchange.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.connection and not self.connection.is_closed:
                return True

            # Create connection with heartbeat and blocked connection timeouts
            parameters = pika.ConnectionParameters(
                host=self.host,
                heartbeat=60,  # Heartbeat every 60 seconds
                blocked_connection_timeout=30,
                connection_attempts=MAX_RETRIES,
                retry_delay=INITIAL_RETRY_DELAY,
            )

            logger.info(f"Attempting to connect to RabbitMQ at {self.host}...")

            try:
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()

                # Declare exchange
                self.channel.exchange_declare(
                    exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
                )

                logger.info("Successfully connected to RabbitMQ")
                return True

            except AMQPConnectionError as e:
                logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
                self.connection = None
                self.channel = None
                return False

        except Exception as e:
            logger.error(f"Unexpected error connecting to RabbitMQ: {str(e)}")
            self.connection = None
            self.channel = None
            return False

        return False

    def publish_event(
        self,
        event_type: EventTypes,
        event: DocumentDiscovered,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish an event to RabbitMQ with retry logic.

        Args:
            event_type: Type of the event (from EventTypes enum)
            event: Event object to publish
            correlation_id: Optional correlation ID to use for this event
                          (will override event's correlation_id if
                          provided)

        Returns:
            bool: True if message was published successfully,
                 False otherwise
        """
        # Use explicitly provided correlation_id or fall back to event's correlationId
        final_correlation_id = correlation_id or event.correlationId
        
        # Convert event to dictionary
        event_data = {
            "eventType": event.eventType,
            "eventId": event.eventId,
            "timestamp": event.timestamp,
            "correlationId": final_correlation_id,  # Use final_correlation_id
            "source": event.source,
            "version": event.version,
            "payload": event.payload,
        }

        for attempt in range(MAX_RETRIES):
            try:
                # Ensure connection is alive
                if not self._ensure_connection():
                    continue

                # Set correlation ID in both message data and properties
                if not self.channel:
                    raise RuntimeError("Channel not initialized")
                self.channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=event_type.value,  # Use event_type value as routing key
                    body=json.dumps(event_data),
                    properties=pika.BasicProperties(
                        correlation_id=final_correlation_id,  # Use final_correlation_id
                        delivery_mode=2,  # Make message persistent
                        content_type="application/json",
                    ),
                )
                logger.info(
                    "Successfully published event",
                    extra={
                        "correlation_id": final_correlation_id,
                        "event_type": event_type.value,
                        "routing_key": event_type.value,
                    },
                )
                return True

            except (AMQPConnectionError, AMQPChannelError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Failed to publish event (attempt "
                        f"{attempt + 1}/{MAX_RETRIES}). "
                        f"Retrying in {wait_time:.2f} seconds... "
                        f"Error: {str(e)}",
                        extra={
                            "correlation_id": final_correlation_id,
                            "event_type": event_type.value,
                            "attempt": attempt + 1,
                            "wait_time": wait_time,
                            "error": str(e),
                        },
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to publish event after {MAX_RETRIES} attempts",
                        extra={
                            "correlation_id": final_correlation_id,
                            "event_type": event_type.value,
                            "error": str(e),
                            "total_attempts": MAX_RETRIES,
                        },
                    )
                    return False

        return False

    def _ensure_connection(self) -> bool:
        """Ensure connection to RabbitMQ is active and healthy.

        Returns:
            bool: True if connection is active or successfully
                 reconnected, False otherwise
        """
        try:
            if self.connection and not self.connection.is_closed:
                # Try to process any pending IO events
                self.connection.process_data_events()
                return True
            return self._connect()
        except (AMQPError, OSError) as e:
            logger.error(f"Connection check failed: {str(e)}")
            self.connection = None
            self.channel = None
            return self._connect()  # Try to establish a fresh connection

    def close(self):
        """Close the connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
                logger.info("Closed RabbitMQ connection")
            except AMQPError as e:
                logger.error(f"Error closing RabbitMQ connection: {str(e)}")
        self.connection = None
        self.channel = None
