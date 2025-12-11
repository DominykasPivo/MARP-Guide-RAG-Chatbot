import json
import logging
import threading
from typing import Any, Callable, Dict, Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

logger = logging.getLogger("chat.rabbitmq")


class RabbitMQClient:
    """RabbitMQ client for publishing and subscribing to messages."""

    def __init__(self, host: str = "localhost", port: int = 5672):
        self.host = host
        self.port = port
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        self.subscriptions: Dict[str, Callable] = {}
        self.consumer_thread: Optional[threading.Thread] = None
        self._connect()

    def _connect(self):
        """Establish connection to RabbitMQ."""
        try:
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def publish(self, routing_key: str, message: Dict[str, Any], exchange: str = ""):
        """Publish a message to a routing key."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")

        try:
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                ),
            )
            logger.info(f"Published message to {routing_key}")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            raise

    def subscribe(
        self,
        routing_key: str,
        callback: Callable[[Dict[str, Any]], None],
        exchange: str = "",
        exchange_type: str = "topic",
    ):
        """Subscribe to messages with a routing key."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")

        try:
            self.channel.exchange_declare(
                exchange=exchange, exchange_type=exchange_type, durable=True
            )
            result = self.channel.queue_declare("", exclusive=True)
            queue_name = result.method.queue
            self.channel.queue_bind(
                exchange=exchange, queue=queue_name, routing_key=routing_key
            )
            self.subscriptions[routing_key] = callback
            self.channel.basic_consume(
                queue=queue_name, on_message_callback=self.on_message, auto_ack=False
            )
            logger.info(f"Subscribed to routing key: {routing_key}")
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            raise

    def on_message(
        self,
        ch: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes,
    ):
        """Handle incoming messages."""
        try:
            message = json.loads(body.decode())
            routing_key = method.routing_key
            if routing_key in self.subscriptions:
                self.subscriptions[routing_key](message)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                logger.warning(f"No callback for routing key: {routing_key}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def start_consuming(self):
        """Start consuming messages in a separate thread."""
        if not self.consumer_thread or not self.consumer_thread.is_alive():
            self.consumer_thread = threading.Thread(target=self._consume)
            self.consumer_thread.daemon = True
            self.consumer_thread.start()
            logger.info("Started message consumer thread")

    def _consume(self):
        """Consume messages (runs in separate thread)."""
        try:
            self.channel.start_consuming()
        except Exception as e:
            logger.error(f"Error in consumer: {e}")

    def close(self):
        """Close the connection."""
        if self.connection:
            self.connection.close()
            logger.info("Closed RabbitMQ connection")
