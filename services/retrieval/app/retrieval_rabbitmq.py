import logging
import os
import random
import time

import pika
from pika.exceptions import AMQPConnectionError

logger = logging.getLogger("retrieval.rabbitmq")

# Constants
EXCHANGE_NAME = "document_events"
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1
MAX_RETRY_DELAY = 60
BACKOFF_MULTIPLIER = 2
JITTER_RANGE = 0.1


class EventConsumer:
    def __init__(self, rabbitmq_host=None, retriever=None):
        """Initialize EventConsumer.

        Args:
            rabbitmq_host: RabbitMQ hostname (defaults to env var)
            retriever: Retriever instance for processing queries
        """
        self.host = rabbitmq_host or os.getenv("RABBITMQ_HOST", "localhost")
        self.connection = None
        self.channel = None
        self.retriever = retriever
        self.subscriptions = {}  # Track subscriptions: {event_type: callback}
        logger.info(f"EventConsumer initialized for host: {self.host}")

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay: float = min(
            INITIAL_RETRY_DELAY * (BACKOFF_MULTIPLIER**attempt), MAX_RETRY_DELAY
        )
        jitter = delay * JITTER_RANGE
        delay += random.uniform(-jitter, jitter)  # nosec B311
        return max(0.0, delay)  # type: ignore[return-value]

    def _connect(self) -> bool:
        """Establish connection to RabbitMQ."""
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
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare exchange according to event catalogue
            self.channel.exchange_declare(
                exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
            )

            logger.info("Successfully connected to RabbitMQ")
            return True

        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to RabbitMQ: {e}")
            return False

    def subscribe(self, event_type: str, callback):
        """Register a subscription (does not start consuming yet).

        Args:
            event_type: Event type to subscribe to (e.g., 'queryreceived')
            callback: Function to call when event is received
        """
        routing_key = event_type.lower()
        self.subscriptions[routing_key] = callback
        logger.info(f"Registered subscription for '{routing_key}' events")

    def start_consuming(self):
        """Start consuming messages for all registered subscriptions."""
        for attempt in range(MAX_RETRIES):
            if not self._connect():
                if attempt < MAX_RETRIES - 1:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Retrying connection in {delay:.2f}s... "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error("Max retries reached. Could not establish connection.")
                    raise ConnectionError(
                        "Failed to connect to RabbitMQ after max retries"
                    )

            try:
                # Set up all subscriptions
                for routing_key, callback in self.subscriptions.items():
                    # Create exclusive queue for this subscription
                    result = self.channel.queue_declare(queue="", exclusive=True)
                    queue_name = result.method.queue

                    # Bind queue to exchange with routing key
                    self.channel.queue_bind(
                        exchange=EXCHANGE_NAME,
                        queue=queue_name,
                        routing_key=routing_key,
                    )

                    # Set up consumer
                    self.channel.basic_qos(prefetch_count=1)
                    self.channel.basic_consume(
                        queue=queue_name, on_message_callback=callback, auto_ack=False
                    )

                    logger.info(
                        f"Subscribed to '{routing_key}' events on "
                        f"exchange '{EXCHANGE_NAME}'"
                    )

                logger.info(
                    f"Starting to consume messages for "
                    f"{len(self.subscriptions)} event types..."
                )
                self.channel.start_consuming()

            except KeyboardInterrupt:
                logger.info("Stopping consumer...")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Error in consumer: {e}")
                if attempt < MAX_RETRIES - 1:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    raise

    def stop(self):
        """Stop consuming and close connection."""
        try:
            if self.channel:
                self.channel.stop_consuming()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("EventConsumer stopped")
        except Exception as e:
            logger.error(f"Error stopping consumer: {e}")
