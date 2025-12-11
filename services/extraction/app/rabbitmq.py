"""RabbitMQ consumer and publisher with retry and recovery."""

import json
import logging
import os
import random
import time
import uuid
from datetime import datetime
from typing import Callable, Optional

import pika
from pika.exceptions import AMQPChannelError, AMQPConnectionError

logger = logging.getLogger("extraction.rabbitmq")

EXCHANGE_NAME = "document_events"
MAX_RETRIES = int(os.getenv("RABBITMQ_MAX_RETRIES", "5"))
INITIAL_RETRY_DELAY = int(os.getenv("RABBITMQ_INITIAL_RETRY_DELAY", "1"))
MAX_RETRY_DELAY = int(os.getenv("RABBITMQ_MAX_RETRY_DELAY", "30"))
JITTER_RANGE = 0.1
CONSUMER_RECONNECT_DELAY = 5
CONNECTION_TIMEOUT = int(os.getenv("RABBITMQ_CONNECTION_TIMEOUT", "30"))


class EventConsumer:
    """Event consumer for RabbitMQ."""

    def __init__(self, host: str = "rabbitmq"):
        self.host = host
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.queue_name: Optional[str] = None
        self.start_time = time.time()
        try:
            self._connect()
        except AMQPConnectionError as e:
            logger.error(f"Initial connection failed: {str(e)}")

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        delay: float = min(INITIAL_RETRY_DELAY * (2**attempt), MAX_RETRY_DELAY)
        jitter = delay * JITTER_RANGE
        delay += random.uniform(-jitter, jitter)  # nosec B311
        return max(0.0, delay)

    def _connect(self) -> bool:
        """Connect to RabbitMQ and declare exchange."""
        try:
            parameters = pika.ConnectionParameters(
                host=self.host,
                heartbeat=60,
                blocked_connection_timeout=CONNECTION_TIMEOUT,
                connection_attempts=MAX_RETRIES,
                retry_delay=INITIAL_RETRY_DELAY,
            )
            logger.info(f"Connecting to RabbitMQ at {self.host}...")
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.exchange_declare(
                exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
            )
            logger.info("RabbitMQ connection established")
            return True
        except AMQPConnectionError as e:
            logger.error(f"RabbitMQ connection failed: {str(e)}")
            return False

    def publish(
        self,
        routing_key: str,
        event_type: str,
        event_data: dict,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish event with retry."""
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            logger.warning(
                "Missing correlation ID; generated new one",
                extra={"correlation_id": correlation_id},
            )

        for attempt in range(MAX_RETRIES):
            try:
                if not self.channel or self.channel.is_closed:
                    if not self._connect():
                        wait = self._calculate_retry_delay(attempt)
                        logger.warning(
                            f"Connection unavailable "
                            f"(attempt {attempt + 1}/{MAX_RETRIES}); "
                            f"retrying in {wait:.2f}s",
                            extra={
                                "correlation_id": correlation_id,
                                "attempt": attempt + 1,
                                "wait_time": wait,
                            },
                        )
                        time.sleep(wait)
                        continue

                message = {
                    "event_type": event_type,
                    "data": event_data,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                if not self.channel:
                    raise RuntimeError("Channel not initialized")

                self.channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=routing_key,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type="application/json",
                        correlation_id=correlation_id,
                        headers={"correlation_id": correlation_id},
                    ),
                )
                logger.info(
                    "Event published",
                    extra={
                        "routing_key": routing_key,
                        "event_type": event_type,
                        "correlation_id": correlation_id,
                        "attempt": attempt + 1,
                    },
                )
                return True

            except (AMQPConnectionError, AMQPChannelError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Publish failed "
                        f"(attempt {attempt + 1}/{MAX_RETRIES}); "
                        f"retrying in {wait:.2f}s: {str(e)}",
                        extra={
                            "correlation_id": correlation_id,
                            "event_type": event_type,
                            "attempt": attempt + 1,
                            "wait_time": wait,
                            "error": str(e),
                        },
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "Publish failed after max retries",
                        extra={
                            "correlation_id": correlation_id,
                            "event_type": event_type,
                            "error": str(e),
                        },
                    )
        return False

    def subscribe(self, event_type: str, callback: Callable) -> bool:
        """Subscribe to an event type."""
        for attempt in range(MAX_RETRIES):
            try:
                if not self.channel or self.channel.is_closed:
                    if not self._connect():
                        wait = self._calculate_retry_delay(attempt)
                        logger.warning(
                            f"Connection unavailable "
                            f"(attempt {attempt + 1}/{MAX_RETRIES}); "
                            f"retrying in {wait:.2f}s"
                        )
                        time.sleep(wait)
                        continue

                self.queue_name = "extraction_queue"
                if not self.channel:
                    raise RuntimeError("Channel not initialized")

                self.channel.queue_declare(queue=self.queue_name, durable=True)
                self.channel.queue_bind(
                    exchange=EXCHANGE_NAME,
                    queue=self.queue_name,
                    routing_key=event_type,
                )
                self.channel.basic_consume(
                    queue=self.queue_name,
                    on_message_callback=lambda ch, method, props, body: (
                        self._handle_message(callback, ch, method, props, body)
                    ),
                    auto_ack=False,
                )
                logger.info(f"Subscribed to '{event_type}'")
                return True

            except (AMQPConnectionError, AMQPChannelError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Subscription failed "
                        f"(attempt {attempt + 1}/{MAX_RETRIES}); "
                        f"retrying in {wait:.2f}s: {str(e)}"
                    )
                    time.sleep(wait)
                else:
                    logger.error(f"Subscription failed after max retries: {str(e)}")
        return False

    def _handle_message(self, callback: Callable, ch, method, props, body):
        """Handle a received message."""
        try:
            correlation_id = None
            message = json.loads(body)
            event_data = message.get("data", {})

            if props:
                if props.correlation_id:
                    correlation_id = props.correlation_id
                elif props.headers and "correlation_id" in props.headers:
                    correlation_id = props.headers["correlation_id"]

            if (
                not correlation_id
                and isinstance(message, dict)
                and "correlation_id" in message
            ):
                correlation_id = message["correlation_id"]

            if not correlation_id:
                correlation_id = str(uuid.uuid4())
                logger.warning(
                    "Missing correlation ID; generated new one",
                    extra={"correlation_id": correlation_id},
                )

            try:
                callback(ch, method, props, body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.debug(
                    "Message acknowledged", extra={"correlation_id": correlation_id}
                )
            except Exception as e:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                logger.error(
                    f"Message processing error; requeued: {str(e)}",
                    extra={"correlation_id": correlation_id, "error": str(e)},
                )

            if not props:
                props = pika.BasicProperties(
                    correlation_id=correlation_id,
                    content_type="application/json",
                    delivery_mode=2,
                )
            elif not props.correlation_id:
                props = pika.BasicProperties(
                    correlation_id=correlation_id,
                    content_type=props.content_type or "application/json",
                    delivery_mode=2,
                )

            logger.info(
                "Message received",
                extra={
                    "correlation_id": correlation_id,
                    "routing_key": method.routing_key if method else None,
                    "document_id": event_data.get("document_id"),
                },
            )
        except Exception as e:
            logger.error("Failed to handle message", extra={"error": str(e)})

    def start_consuming(self):
        """Start consuming."""
        try:
            if self.channel:
                logger.info("Starting consumer")
                self.channel.start_consuming()
            else:
                logger.error("No channel available for consuming")
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Consumer error: {str(e)}")
            self.connection = None
            self.channel = None
