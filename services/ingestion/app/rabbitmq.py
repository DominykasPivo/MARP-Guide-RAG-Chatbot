"""RabbitMQ event publisher for the ingestion service with retry logic."""

import json
import logging
import os
import random
from typing import Optional

import pika
from events import DocumentDiscovered, EventTypes
from pika.exceptions import AMQPChannelError, AMQPConnectionError, AMQPError

logger = logging.getLogger("ingestion.rabbitmq")

MAX_RETRIES = int(os.getenv("RABBITMQ_MAX_RETRIES", "5"))
INITIAL_RETRY_DELAY = int(os.getenv("RABBITMQ_INITIAL_RETRY_DELAY", "1"))
MAX_RETRY_DELAY = int(os.getenv("RABBITMQ_MAX_RETRY_DELAY", "30"))
JITTER_RANGE = 0.1
CONNECTION_TIMEOUT = int(os.getenv("RABBITMQ_CONNECTION_TIMEOUT", "30"))
EXCHANGE_NAME = "document_events"


class EventPublisher:
    """Publish events to RabbitMQ with reconnection and retries."""

    def __init__(self, host: str = "localhost"):
        self.host = host
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        try:
            self._connect()
        except AMQPError as e:
            logger.error(f"Initial connection failed: {str(e)}")

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay: float = min(INITIAL_RETRY_DELAY * (2**attempt), MAX_RETRY_DELAY)
        jitter = delay * JITTER_RANGE
        delay += random.uniform(-jitter, jitter)  # nosec B311
        return max(0.0, delay)

    def _connect(self) -> bool:
        """Establish connection to RabbitMQ and set up the exchange."""
        try:
            if self.connection and not self.connection.is_closed:
                return True

            parameters = pika.ConnectionParameters(
                host=self.host,
                heartbeat=60,
                blocked_connection_timeout=30,
                connection_attempts=MAX_RETRIES,
                retry_delay=INITIAL_RETRY_DELAY,
            )

            logger.info(f"Connecting to RabbitMQ at {self.host}...")
            try:
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                self.channel.exchange_declare(
                    exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
                )
                logger.info("RabbitMQ connection established.")
                return True
            except AMQPConnectionError as e:
                logger.error(f"Connection to RabbitMQ failed: {str(e)}")
                self.connection = None
                self.channel = None
                return False

        except Exception as e:
            logger.error(f"Unexpected connection error: {str(e)}")
            self.connection = None
            self.channel = None
            return False

    def publish_event(
        self,
        event_type: EventTypes,
        event: DocumentDiscovered,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish an event to RabbitMQ with retry logic."""
        final_correlation_id = correlation_id or event.correlationId

        event_data = {
            "eventType": event.eventType,
            "eventId": event.eventId,
            "timestamp": event.timestamp,
            "correlationId": final_correlation_id,
            "source": event.source,
            "version": event.version,
            "payload": event.payload,
        }

        for attempt in range(MAX_RETRIES):
            try:
                if not self._ensure_connection():
                    continue

                if not self.channel:
                    raise RuntimeError("Channel not initialized")

                self.channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=event_type.value,
                    body=json.dumps(event_data),
                    properties=pika.BasicProperties(
                        correlation_id=final_correlation_id,
                        delivery_mode=2,
                        content_type="application/json",
                    ),
                )
                logger.info(
                    "Event published.",
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
                        f"Publish attempt {attempt + 1}/{MAX_RETRIES} "
                        f"failed. Retrying in {wait_time:.2f}s: {str(e)}",
                        extra={
                            "correlation_id": final_correlation_id,
                            "event_type": event_type.value,
                            "attempt": attempt + 1,
                            "wait_time": wait_time,
                            "error": str(e),
                        },
                    )
                else:
                    logger.error(
                        f"Publish failed after {MAX_RETRIES} attempts.",
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
        """Ensure the connection to RabbitMQ is active or re-establish it."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.process_data_events()
                return True
            return self._connect()
        except (AMQPError, OSError) as e:
            logger.error(f"Connection check failed: {str(e)}")
            self.connection = None
            self.channel = None
            return self._connect()

    def close(self) -> None:
        """Close the connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
                logger.info("RabbitMQ connection closed.")
            except AMQPError as e:
                logger.error(f"Error closing RabbitMQ connection: {str(e)}")
        self.connection = None
        self.channel = None


def get_connection(
    max_retries: int = 5, retry_delay: Optional[int] = None
) -> Optional[pika.BlockingConnection]:
    """Get RabbitMQ connection with retries."""
    if retry_delay is None:
        retry_delay = random.randint(1, 5)
    return None


def consume_messages(queue: str, callback, max_retries: Optional[int] = None):
    pass
